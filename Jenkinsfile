def ecr_token
def BUILD_ENVIRONMENT
def ECR_CREDENTIALS
pipeline {

  agent any

  environment {
    BUILDER_NAME = 'k8s-builder'
    DOCKER_REGISTRY = '578061096415.dkr.ecr.us-east-1.amazonaws.com'
    IMAGE_NAME = 'appointment-capacity-chatbot'
    PLATFORMS = 'linux/amd64,linux/arm64'
    GIT_REPO_URL = 'https://github.com/mykaarma/appointment-capacity-chatbot.git'
    GIT_REPO_PATH = './'
  }

  parameters {
    string(name: 'branch', defaultValue: 'main', description: 'The branch to build')
  }

  stages {
    stage("Source Code Management") {
      steps {
        script {
          checkout([
            $class: 'GitSCM',
            branches: [[name: "${params.branch}"]],
            userRemoteConfigs: [[
              url: "${GIT_REPO_URL}",
              credentialsId: 'git_credentials'
            ]]
          ])
        }
      }
    }

    stage('Docker Login') {
      steps {
        // Perform Docker login to ECR using Amazon ECR Credential Helper
        container('aws-cli') {
          script {
            def url = env.EXTERNAL_JENKINS_URL
            if (url.contains("qa-")) {
              BUILD_ENVIRONMENT = 'qa-aws'
              ECR_CREDENTIALS = 'qa-ecr'
            } else {
              BUILD_ENVIRONMENT = 'prod'
              ECR_CREDENTIALS = 'ecr'
            }
            withCredentials([aws(credentialsId: "${ECR_CREDENTIALS}")]){
              ecr_token = sh(script: "aws ecr get-login-password --region us-east-1", returnStdout: true).trim()
            }
          }
        }
      }
    }

    stage("Build image") {
      steps {
        container('docker') {
          script {                
            def builderExists = sh(script: "docker buildx ls  | grep ${BUILDER_NAME}", returnStatus: true)
            if (builderExists != 0) {
              sh "docker buildx create --bootstrap --name ${BUILDER_NAME} --driver kubernetes --platform=linux/amd64 --node=builder-amd64 --driver-opt replicas=1,nodeselector=\"kubernetes.io/arch=amd64\" --use"
              sh "docker buildx create --append --bootstrap --name ${BUILDER_NAME} --driver kubernetes --platform=linux/arm64 --node=builder-arm64 --driver-opt replicas=1,nodeselector=\"kubernetes.io/arch=arm64\" --use"
            }
            dir(env.GIT_REPO_PATH) {
              def VERSION = readFile('version.txt').split('=')[1].trim()    
              sh "docker login --username AWS --password ${ecr_token} ${DOCKER_REGISTRY}"
              def pushOutput = sh script: "docker buildx build -f Dockerfile --builder ${BUILDER_NAME} --build-arg ENVIRONMENT=${BUILD_ENVIRONMENT} \
                                          --platform ${PLATFORMS}  -t ${DOCKER_REGISTRY}/${IMAGE_NAME}:${VERSION} --push --provenance false . 2>&1",returnStdout: true
              echo "${pushOutput}"
              if (pushOutput.contains('ERROR')){
                error "Docker build failed with Error in build and Push"
              }
            }
          }
        }
      }
    }
  }
}

