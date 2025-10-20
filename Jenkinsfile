pipeline {
  agent any

  options { timestamps() }

  environment {
    VENV = "${WORKSPACE}/.venv"
    SSHINFO_CSV = "${WORKSPACE}/data/ssh/sshInfo.csv"
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Create venv & install deps') {
      steps {
        sh '''
          set -e
          python3 -m venv "$VENV"
          . "$VENV/bin/activate"
          python -m pip install --upgrade pip wheel
          pip install coverage jinja2 pyyaml ipaddress art InquirerPy rich termcolor loguru
          pip install netmiko paramiko
        '''
      }
    }

    stage('Unit Tests + Coverage') {
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

    stage('Archive coverage artifacts (optional)') {
      steps {
        archiveArtifacts artifacts: 'coverage_html/**, coverage.json, .coverage', fingerprint: true
      }
    }
  }

  post {
    success { echo '✅ Unit tests + coverage complete.' }
    failure { echo '❌ Pipeline failed — see stage logs.' }
  }
}
