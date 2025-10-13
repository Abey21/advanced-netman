pipeline {
  agent any
  triggers { githubPush() }   // run when GitHub webhook fires

  environment {
    PING_SCRIPT = 'scripts/ping_webserver.py'
    SSH_CSV     = 'data/ssh/sshInfo.csv'
    DST_IP      = '1.1.1.2'
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Verify files') {
      steps {
        sh '''
          echo "WORKSPACE=$WORKSPACE"
          test -f "${PING_SCRIPT}" || { echo "Missing ${PING_SCRIPT}"; exit 2; }
          test -f "${SSH_CSV}"     || { echo "Missing ${SSH_CSV}"; exit 2; }
          head -n 3 "${SSH_CSV}" || true
        '''
      }
    }

    stage('Install deps') {
      steps {
        sh '''
          python3 -m pip install --user --upgrade pip
          python3 -m pip install --user netmiko rich pandas
        '''
      }
    }

    stage('Ping webserver from devices') {
      steps {
        sh '''
          mkdir -p reports
          python3 "${PING_SCRIPT}" --csv "${SSH_CSV}" --dst "${DST_IP}" \
            | tee reports/ping_report.txt
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'reports/*.txt', onlyIfSuccessful: false
    }
  }
}
