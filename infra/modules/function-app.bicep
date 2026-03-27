// ---------------------------------------------------------------------------
// Module: function-app.bicep
// Deploys Azure Functions as a Container App (custom Docker container)
// inside the shared Container Apps Environment.
// Reusable module — called once per function with per-function env vars.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Short function identifier used in naming: func-{functionName}-{baseName}. Empty string produces func-{baseName}.')
param functionName string

@description('AZD service name tag value for azure.yaml mapping')
param azdServiceName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Storage account name for Functions runtime (shared, created externally)')
param functionsStorageAccountName string

@description('Per-function environment variable array')
param envVars array

@description('Principal ID of the deployer (human user) for storage access')
param deployerPrincipalId string = ''

@description('ACR login server (e.g., cr{project}dev.azurecr.io)')
param acrLoginServer string

@description('ACR resource ID for role assignment')
param acrResourceId string

@description('Container Apps Environment resource ID')
param containerAppsEnvId string

@description('Docker image name and tag. Leave empty for initial provisioning.')
param imageName string = ''

// Use a public placeholder image on first deploy (before AZD pushes the real image).
// The Functions base image does not start a healthy revision without mounted app code,
// so use a simple HTTP placeholder until azd deploy swaps in the real image.
var useAcrImage = !empty(imageName)
var containerImage = useAcrImage ? '${acrLoginServer}/${imageName}' : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// When functionName is empty, produce the same name as before: func-{baseName}
var containerAppName = empty(functionName) ? 'func-${baseName}' : 'func-${functionName}-${baseName}'

// ---------------------------------------------------------------------------
// Reference: Shared Functions runtime storage account (created in main.bicep)
// ---------------------------------------------------------------------------
resource functionsStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: functionsStorageAccountName
}

// ---------------------------------------------------------------------------
// Function App as a Container App
// (Runs inside the shared Container Apps Environment)
// ---------------------------------------------------------------------------
resource functionApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': azdServiceName
  })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
      }
      // Only attach ACR registry config when the deployed image actually lives in ACR.
      // The placeholder MCR image does not need registry auth during provision.
      registries: useAcrImage ? [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: 'functions'
          image: containerImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 5
        rules: [
          {
            name: 'http-trigger'
            http: {
              metadata: {
                concurrentRequests: '1'
              }
            }
          }
        ]
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role: AcrPull on ACR for function app managed identity
// (Must be in the same module as the Container App to avoid circular dependency
// between the Container App needing ACR access and ACR role needing the principal ID)
// ---------------------------------------------------------------------------
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, functionApp.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}

// Reference the existing ACR (for scoping the role assignment)
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: split(acrResourceId, '/')[8]
}

// ---------------------------------------------------------------------------
// Role: Storage Blob Data Owner on the Functions storage account
// (Required for AzureWebJobsStorage managed identity access)
// ---------------------------------------------------------------------------
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'

resource funcStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionsStorage.id, functionApp.id, storageBlobDataOwnerRoleId)
  scope: functionsStorage
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role: Storage Blob Data Owner for the deployer (human user)
// ---------------------------------------------------------------------------
resource deployerStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(functionsStorage.id, deployerPrincipalId, storageBlobDataOwnerRoleId)
  scope: functionsStorage
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppFqdn string = functionApp.properties.configuration.ingress.fqdn
output functionAppUrl string = 'https://${functionApp.properties.configuration.ingress.fqdn}'
