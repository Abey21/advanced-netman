pipeline {
  agent any

  environment {
    VENV = "${WORKSPACE}/.venv"
    CSV  = "data/ssh/sshInfo.csv"
    DST  = "1.1.1.2"

    // Change this regex if you want to exclude different devices later
    EXCLUDE_REGEX = "^(S1|S2),"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Verify files') {
      steps {
        sh '''
          echo "WORKSPACE=$WORKSPACE"
          test -f scripts/ping_webserver.py
          test -f "$CSV"
          head -n 3 "$CSV"
        '''
      }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''
          python3 -m venv "$VENV"
          . "$VENV/bin/activate"
          python -m pip install --upgrade pip wheel
          python -m pip install netmiko rich loguru
        '''
      }
    }

    stage('Filter CSV (exclude S1,S2)') {
      steps {
        sh '''
          mkdir -p artifacts
          # Keep header, then filter out rows that start with S1, S2
          { head -n 1 "$CSV"; tail -n +2 "$CSV" | grep -Ev "$EXCLUDE_REGEX"; } > artifacts/sshInfo.filtered.csv
          echo "Filtered CSV preview:"
          cat artifacts/sshInfo.filtered.csv
        '''
      }
    }

    stage('Ping webserver from devices') {
      steps {
        sh '''
          . "$VENV/bin/activate"
          echo "Ping destination: $DST"
          echo "Using CSV: artifacts/sshInfo.filtered.csv"
          python scripts/ping_webserver.py --csv artifacts/sshInfo.filtered.csv --dst "$DST"
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
    }
  }
}
