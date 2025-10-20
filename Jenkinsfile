pipeline {
  agent any

  options {
    timestamps()
    // ansiColor('xterm')  // keep commented; not supported on your controller
  }

  environment {
    VENV        = "${WORKSPACE}/.venv"
    SSHINFO_CSV = "${WORKSPACE}/data/ssh/sshInfo.csv"

    // optional legacy vars
    CSV           = "data/ssh/sshInfo.csv"
    DST           = "1.1.1.2"
    EXCLUDE_REGEX = "^(S1|S2),"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''
          set -e
          python3 -m venv "$VENV"
          . "$VENV/bin/activate"
          python -m pip install --upgrade pip wheel

          # test + coverage + templating
          pip install coverage jinja2 pyyaml ipaddress

          # libs imported by scripts/health_check.py
          pip install art InquirerPy rich termcolor loguru

          # device libs (imported at import-time by health_check.py)
          pip install netmiko paramiko
        '''
      }
    }

    // Optional: lint templates if you use them (keep commented unless needed)
    // stage('Lint Jinja2 Templates') {
    //   when { expression { return fileExists("template-generator/templates") } }
    //   steps {
    //     sh '''
    //       . "$VENV/bin/activate"
    //       pip install j2lint
    //       j2lint template-generator/templates
    //     '''
    //   }
    // }

    stage('Unit Tests + Coverage (mocked)') {
      steps {
        sh '''
          set -e
          . "$VENV/bin/activate"
          export PYTHONPATH="$WORKSPACE"
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

    // ===== Optional: your earlier CSV filter + ping stages =====
    stage('Verify CSV present') {
      steps {
        sh '''
          set -e
          test -f "$CSV" || { echo "Missing $CSV"; exit 1; }
          head -n 3 "$CSV" || true
        '''
      }
    }

    stage('Filter CSV (exclude S1,S2)') {
      steps {
        sh '''
          set -e
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
          set -e
          . "$VENV"/bin/activate
          echo "Ping destination: $DST"
          echo "Using CSV: artifacts/sshInfo.filtered.csv"
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
