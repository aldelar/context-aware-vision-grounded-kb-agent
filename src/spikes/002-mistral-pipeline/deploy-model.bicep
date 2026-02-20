// ---------------------------------------------------------------------------
// Spike 002: Deploy mistral-document-ai-2512 to existing Foundry resource
// ---------------------------------------------------------------------------
// Follows the pattern from:
//   https://github.com/Azure-Samples/azureai-model-inference-bicep
//
// Usage:
//   az deployment group create \
//     --resource-group <rg> \
//     --template-file deploy-model.bicep \
//     --parameters accountName=<ai-services-name>
// ---------------------------------------------------------------------------

@description('Name of the existing Azure AI Services (Foundry) account')
param accountName string

@description('Deployment name for the model')
param deploymentName string = 'mistral-document-ai-2512'

@description('Model name in the Foundry catalog')
param modelName string = 'mistral-document-ai-2512'

@description('Model version')
param modelVersion string = '1'

@description('Model provider format')
@allowed([
  'Mistral AI'
  'OpenAI'
])
param modelPublisherFormat string = 'Mistral AI'

@description('Deployment SKU')
param skuName string = 'GlobalStandard'

@description('Deployment capacity')
param capacity int = 1

// ---------------------------------------------------------------------------
// Model deployment on existing AI Services account
// ---------------------------------------------------------------------------
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  name: '${accountName}/${deploymentName}'
  sku: {
    name: skuName
    capacity: capacity
  }
  properties: {
    model: {
      format: modelPublisherFormat
      name: modelName
      version: modelVersion
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output deploymentName string = modelDeployment.name
output modelName string = modelName
output modelFormat string = modelPublisherFormat
