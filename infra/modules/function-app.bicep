// ---------------------------------------------------------------------------
// Module: function-app.bicep
// Deploys Azure Functions (Python, Flex Consumption plan)
// with system-assigned managed identity
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Storage account name for Functions runtime (uses the staging account)')
param functionsStorageAccountName string

@description('Staging storage blob endpoint')
param stagingBlobEndpoint string

@description('Serving storage blob endpoint')
param servingBlobEndpoint string

@description('Azure AI Services endpoint')
param aiServicesEndpoint string

@description('Embedding deployment name')
param embeddingDeploymentName string

@description('Azure AI Search endpoint')
param searchEndpoint string

@description('Azure AI Search index name')
param searchIndexName string = 'kb-articles'

// ---------------------------------------------------------------------------
// Flex Consumption Plan
// ---------------------------------------------------------------------------
resource flexPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${baseName}'
  location: location
  tags: tags
  kind: 'functionapp'
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  properties: {
    reserved: true // Linux
  }
}

// ---------------------------------------------------------------------------
// Storage account for Functions runtime
// (Dedicated account, separate from staging/serving)
// ---------------------------------------------------------------------------
resource functionsStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: functionsStorageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

// ---------------------------------------------------------------------------
// Function App (Python 3.11, Flex Consumption)
// ---------------------------------------------------------------------------
resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: 'func-${baseName}'
  location: location
  tags: union(tags, {
    'azd-service-name': 'functions'
  })
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: flexPlan.id
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${functionsStorage.properties.primaryEndpoints.blob}deployments'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: functionsStorage.name
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        // --- Application settings ---
        {
          name: 'STAGING_BLOB_ENDPOINT'
          value: stagingBlobEndpoint
        }
        {
          name: 'SERVING_BLOB_ENDPOINT'
          value: servingBlobEndpoint
        }
        {
          name: 'AI_SERVICES_ENDPOINT'
          value: aiServicesEndpoint
        }
        {
          name: 'EMBEDDING_DEPLOYMENT_NAME'
          value: embeddingDeploymentName
        }
        {
          name: 'SEARCH_ENDPOINT'
          value: searchEndpoint
        }
        {
          name: 'SEARCH_INDEX_NAME'
          value: searchIndexName
        }
      ]
    }
  }
}

// ---------------------------------------------------------------------------
// Role: Storage Blob Data Owner on the Functions storage account
// (Required for Flex Consumption deployment + AzureWebJobsStorage)
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
// Outputs
// ---------------------------------------------------------------------------
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppDefaultHostname string = functionApp.properties.defaultHostName
