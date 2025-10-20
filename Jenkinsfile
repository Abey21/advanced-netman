pipeline {
  agent any

  options { timestamps(); ansiColor('xterm') }

  environment {
    VENV = "${WORKSPACE}/.venv"
    SSHINFO_CSV = "${WORKSPACE}/data/ssh/sshInfo.csv"
    // For your previous optional stages:
    CSV  = "data/ssh/sshInfo.csv"
    DST  = "1.1.1.2"
    EXCLUDE_REGEX = "^(S1|S2),"
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''
          python3 -m venv "$VENV"
          . "$VENV/bin/activate"
          python -m pip install --upgrade pip wheel
          # deps for unit tests + coverage
          pip install coverage jinja2 pyyaml ipaddress
          # If health_check imports netmiko at import-time, install it (even if mocked later)
          pip install netmiko paramiko
          # Optional: j2lint if you want a template lint stage
          # pip install j2lint
        '''
      }
    }

    // Optional: template lint (uncomment if you use it)
    // stage('Lint Jinja2 Templates') {
    //   when { expression { return fileExists("template-generator/templates") } }
    //   steps {
    //     sh '''
    //       . "$VENV/bin/activate"
    //       j2lint template-generator/templates
    //     '''
    //   }
    // }

    stage('Unit Tests + Coverage (mocked)') {
      steps {
        sh '''
          . "$VENV/bin/activate"
          export SSHINFO_CSV="${SSHINFO_CSV}"
          coverage run --source=scripts -m unittest discover -s scripts -p "test_*.py"
          coverage html
          coverage json
          coverage report -m
        '''
      }
    }

    stage('Archive Coverage Report') {
      steps {
        archiveArtifacts artifacts: 'coverage_html/**, coverage.json, .coverage', fingerprint: true
        publishHTML(target: [
          allowMissing: false,
          alwaysLinkToLastBuild: true,
          keepAll: true,
          reportDir: 'coverage_html',
          reportFiles: 'index.html',
          reportName: 'Coverage HTML'
        ])
      }
    }

    // ===== Optional: keep your earlier CSV filter + ping stages =====
    stage('Verify CSV present') {
      steps {
        sh '''
          test -f "$CSV" || { echo "Missing $CSV"; exit 1; }
          head -n 3 "$CSV" || true
        '''
      }
    }

    stage('Filter CSV (exclude S1,S2)') {
      steps {
        sh '''
          mkdir -p artifacts
          { head -n 1 "$CSV"; tail -n +2 "$CSV" | grep -Ev "$EXCLUDE_REGEX"; } > artifacts/sshInfo.filtered.csv
          echo "Filtered CSV preview:"
          cat artifacts/sshInfo.filtered.csv
        '''
      }
    }

    stage('Ping webserver from devices (optional)') {
      steps {
        sh '''
          . "$VENV/bin/activate"
          echo "Ping destination: $DST"
          echo "Using CSV: artifacts/sshInfo.filtered.csv"
          # Only run if your script exists:
          if [ -f scripts/ping_webserver.py ]; then
            python scripts/ping_webserver.py --csv artifacts/sshInfo.filtered.csv --dst "$DST"
          else
            echo "scripts/ping_webserver.py not found; skipping"
          fi
        '''
      }
    }
    // ===== End optional =====
  }

  post {
    success { echo '✅ Unit tests + coverage complete (mocked), reports published.' }
    failure { echo '❌ Pipeline failed — see stage logs.' }
  }
}
