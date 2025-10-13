pipeline {
  agent any

  environment {
    VENV = ".venv"
    PY   = "${WORKSPACE}/${VENV}/bin/python"
    PIP  = "${WORKSPACE}/${VENV}/bin/pip"
  }

  stages {
    stage('Checkout') {
      steps {
        checkout([
          $class: 'GitSCM',
          branches: [[name: '*/main']],
          userRemoteConfigs: [[
            url: 'https://github.com/Abey21/advanced-netman.git',
            credentialsId: '099056a1-85db-4092-b54d-cd8544650ace'
          ]]
        ])
      }
    }

    stage('Verify files') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          echo "WORKSPACE=${WORKSPACE}"
          test -f scripts/ping_webserver.py
          test -f data/ssh/sshInfo.csv
          head -n 3 data/ssh/sshInfo.csv
        '''
      }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          python3 -m venv "${VENV}"
          . "${VENV}/bin/activate"
          python -m pip install --upgrade pip wheel
          pip install netmiko rich loguru
        '''
      }
    }

    stage('Ping webserver from devices') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          . "${VENV}/bin/activate"
          "${PY}" scripts/ping_webserver.py --csv data/ssh/sshInfo.csv --dst 1.1.1.2 | tee ping_results.txt
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'ping_results.txt', onlyIfSuccessful: false
    }
  }
}
