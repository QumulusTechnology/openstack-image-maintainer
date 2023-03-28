pipeline {
  agent {
    kubernetes {
      yaml """
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  containers:
  - name: ubuntu
    image: repo.qumulus.io/jenkins/jenkins-inbound-agent-ubuntu-jammy:1.0.2
    imagePullPolicy: IfNotPresent
    resources:
      limits:
        cpu: "1000m"
        memory: "1Gi"
        ephemeral-storage: "5Gi"
      requests:
        cpu: "1000m"
        memory: "1Gi"
        ephemeral-storage: "5Gi"
    command:
    - sleep
    args:
    - 9999999
  imagePullSecrets:
  - name: qumulus-repo-docker-credentials
"""
    }
  }
  stages {
    stage('Upload images') {
      steps {
        container(name: 'ubuntu', shell: '/bin/bash') {
            withCredentials([file(credentialsId: 'openstack-credentials', variable: 'OPENSTACK_RC_FILE')]) {
                script {
                    env.OS_PROJECT_DOMAIN_NAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_PROJECT_DOMAIN_NAME', returnStdout: true).trim()
                    env.OS_USER_DOMAIN_NAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_USER_DOMAIN_NAME', returnStdout: true).trim()
                    env.OS_PROJECT_NAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_PROJECT_NAME', returnStdout: true).trim()
                    env.OS_TENANT_NAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_PROJECT_NAME', returnStdout: true).trim()
                    env.OS_PROJECT_ID = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_PROJECT_ID', returnStdout: true).trim()
                    env.OS_REGION_NAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_REGION_NAME', returnStdout: true).trim()
                    env.OS_USERNAME = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_USERNAME', returnStdout: true).trim()
                    env.OS_PASSWORD = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_PASSWORD', returnStdout: true).trim()
                    env.OS_AUTH_URL = sh(script:'. $OPENSTACK_RC_FILE ; echo $OS_AUTH_URL', returnStdout: true).trim()
                }

            sh '''
            export OS_AUTH_URL="${OS_AUTH_URL}"
            python3 -u ./download-latest-linux-images.py
            '''
          }
        }
      }
    }
  }
}
