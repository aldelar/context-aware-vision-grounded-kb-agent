// ---------------------------------------------------------------------------
// Module: ai-services.bicep
// Deploys Azure AI Services (Foundry) account with model deployments.
// RBAC is handled separately by ai-services-role.bicep.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

// ---------------------------------------------------------------------------
// Azure AI Services Account (Foundry resource)
// Provides: Content Understanding, OpenAI model hosting
// ---------------------------------------------------------------------------
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'ai-${baseName}'
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'ai-${baseName}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    allowProjectManagement: true
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: text-embedding-3-small (for fn-index)
// ---------------------------------------------------------------------------
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'text-embedding-3-small'
  sku: {
    name: 'GlobalStandard'
    capacity: 120 // 120K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: text-embedding-3-large (required by CU prebuilt-documentSearch)
// CU documentSearch internally uses text-embedding-3-large for field extraction;
// silently returns 0 contents if this model is not deployed and registered.
// ---------------------------------------------------------------------------
resource embeddingLargeDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'text-embedding-3-large'
  dependsOn: [embeddingDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 120 // 120K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: gpt-5-mini (for future agent)
// ---------------------------------------------------------------------------
resource agentDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-5-mini'
  dependsOn: [embeddingLargeDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 30 // 30K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: gpt-4.1 (for Content Understanding custom analyzers)
// CU requires a completion model from its supported list:
//   gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano
// ---------------------------------------------------------------------------
resource cuCompletionDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-4.1'
  dependsOn: [agentDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 30 // 30K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: '2025-04-14'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: gpt-4.1-mini (required by CU prebuilt-documentSearch)
// prebuilt-documentSearch internally requires gpt-4.1-mini; fails with
// "No deployment for model 'gpt-4.1-mini' was provided" if missing.
// ---------------------------------------------------------------------------
resource cuCompletionMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-4.1-mini'
  dependsOn: [cuCompletionDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 30 // 30K tokens per minute
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
  }
}

// ---------------------------------------------------------------------------
// Model Deployment: mistral-document-ai-2512 (for fn_convert_mistral)
// Used by the Mistral Document AI conversion backend for OCR.
// Requires API version 2024-04-01-preview and Mistral AI format.
// ---------------------------------------------------------------------------
resource mistralDocAiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: aiServices
  name: 'mistral-document-ai-2512'
  dependsOn: [cuCompletionMiniDeployment] // Serial deployment to avoid conflicts
  sku: {
    name: 'GlobalStandard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'Mistral AI'
      name: 'mistral-document-ai-2512'
      version: '1'
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output aiServicesId string = aiServices.id
output aiServicesName string = aiServices.name
output aiServicesEndpoint string = aiServices.properties.endpoint
output aiServicesPrincipalId string = aiServices.identity.principalId
output embeddingDeploymentName string = embeddingDeployment.name
output agentDeploymentName string = agentDeployment.name
output cuCompletionDeploymentName string = cuCompletionDeployment.name
output mistralDeploymentName string = mistralDocAiDeployment.name
