// ---------------------------------------------------------------------------
// Module: search.bicep
// Deploys Azure AI Search service (Basic tier)
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Search service SKU')
@allowed(['free', 'basic', 'standard'])
param skuName string = 'basic'

@description('Principal ID to grant Search Index Data Contributor role')
param indexContributorPrincipalId string = ''

// ---------------------------------------------------------------------------
// Azure AI Search
// ---------------------------------------------------------------------------
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: 'srch-${baseName}'
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    partitionCount: 1
    replicaCount: 1
    semanticSearch: 'free'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Search Index Data Contributor
// Allows the Function App to push documents to the index
// ---------------------------------------------------------------------------
var searchIndexDataContributorRoleId = '8bbe4f3e-f3ed-4a68-b546-e74b3c6b0ace' // Search Index Data Contributor

resource searchIndexContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(indexContributorPrincipalId)) {
  name: guid(search.id, indexContributorPrincipalId, searchIndexDataContributorRoleId)
  scope: search
  properties: {
    principalId: indexContributorPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Search Service Contributor
// Allows the Function App to create/manage indexes
// ---------------------------------------------------------------------------
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor

resource searchServiceContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(indexContributorPrincipalId)) {
  name: guid(search.id, indexContributorPrincipalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    principalId: indexContributorPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output searchId string = search.id
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
