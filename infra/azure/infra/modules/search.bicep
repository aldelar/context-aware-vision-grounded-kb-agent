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

@description('Principal ID to grant Search Index Data Contributor role (service principal / managed identity)')
param indexContributorPrincipalId string = ''

@description('Principal ID of the deployer (human user) for Search access')
param deployerPrincipalId string = ''

@description('Principal ID to grant Search Index Data Reader role (e.g., Container App MI for read-only query access)')
param indexReaderPrincipalId string = ''

@description('Principal ID to grant Search Service Contributor role only (e.g., agent MI for agentic retrieval)')
param serviceContributorOnlyPrincipalId string = ''

// ---------------------------------------------------------------------------
// Azure AI Search
// ---------------------------------------------------------------------------
resource search 'Microsoft.Search/searchServices@2023-11-01' = {
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
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor

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
// Role Assignments for deployer (User principal type)
// ---------------------------------------------------------------------------
resource deployerSearchIndexContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(search.id, deployerPrincipalId, searchIndexDataContributorRoleId)
  scope: search
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalType: 'User'
  }
}

resource deployerSearchServiceContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(search.id, deployerPrincipalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalType: 'User'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Search Index Data Reader (read-only, e.g., Container App MI)
// ---------------------------------------------------------------------------
var searchIndexDataReaderRoleId = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource searchIndexReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(indexReaderPrincipalId)) {
  name: guid(search.id, indexReaderPrincipalId, searchIndexDataReaderRoleId)
  scope: search
  properties: {
    principalId: indexReaderPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReaderRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Role Assignment: Search Service Contributor only (e.g., agent MI for agentic retrieval)
// ---------------------------------------------------------------------------
resource searchServiceContributorOnlyRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(serviceContributorOnlyPrincipalId)) {
  name: guid(search.id, serviceContributorOnlyPrincipalId, searchServiceContributorRoleId)
  scope: search
  properties: {
    principalId: serviceContributorOnlyPrincipalId
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
