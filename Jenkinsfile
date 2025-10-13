pipeline {
  agent any

  environment {
    // Set default excludes here if you want to skip certain devices (optional)
    PING_EXCLUDE = "S1,S2"
    PYTHON = "${WORKSPACE}/.venv/bin/python3"
    PIP    = "${WORKSPACE}/.venv/bin/pip"
  }

  options {
    timestamps()
    ansiColor('xterm')
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  triggers {
    // If your GitHub webhook is configured, this will auto-trigger on pushes
    githubPush()
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
          echo "WORKSPACE=${WORKSPACE}"
          test -f scripts/ping_webserver.py
          test -f data/ssh/sshInfo.csv
          head -n 3 data/ssh/sshInfo.csv
        '''
      }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''
          python3 -m venv .venv
          ${PIP} install --upgrade pip wheel
          ${PIP} install netmiko rich loguru
        '''
      }
    }

    stage('Ping webserver from devices') {
      steps {
        script {
          // Run script; capture return code (non-zero means some devices failed)
          def rc = sh(returnStatus: true, script: """
            source .venv/bin/activate
            ${PYTHON} scripts/ping_webserver.py \
              --csv data/ssh/sshInfo.csv \
              --dst 1.1.1.2 \
              --count 5 \
              --exclude "${PING_EXCLUDE}"
          """)

          // Mark the build UNSTABLE (yellow) instead of FAILURE (red)
          if (rc != 0) {
            currentBuild.result = 'UNSTABLE'
            echo "Some devices failed ping. Marking build as UNSTABLE."
          }
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'artifacts/**', fingerprint: true
    }
    unstable {
      echo 'Ping job had failures. Check artifacts/ping_report.txt and artifacts/netmiko/*.log'
    }
  }
}
