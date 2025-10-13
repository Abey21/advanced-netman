pipeline {
  agent any

  environment {
    PY   = "${WORKSPACE}/.venv/bin/python"
    PIP  = "${WORKSPACE}/.venv/bin/pip"
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
          test -f data/ssh/sshInfo.csv
          head -n 3 data/ssh/sshInfo.csv
        '''
      }
    }

    stage('Create venv & install deps') {
      steps {
        // Use bash so we can 'source' reliably
        sh '''#!/usr/bin/env bash
          set -euo pipefail

          # Create the venv if it doesn't exist yet
          if [ ! -x ".venv/bin/python" ]; then
            python3 -m venv .venv
          fi

          # Upgrade pip/wheel into the venv and install required libs
          . .venv/bin/activate
          pip install --upgrade pip wheel
          pip install netmiko rich loguru
        '''
      }
    }

    stage('Ping webserver from devices') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          . .venv/bin/activate
          ${PY} scripts/ping_webserver.py
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts allowEmptyArchive: true, artifacts: 'ping_results.*'
    }
    success {
      echo 'Ping job completed successfully.'
    }
    failure {
      echo 'Ping job failed. Check Console Output for details.'
    }
  }
}
