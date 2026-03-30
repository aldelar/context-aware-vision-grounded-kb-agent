// ---------------------------------------------------------------------------
// Module: apim.bicep
// Provisions Azure API Management as an AI Gateway for agent traffic.
// Enables Foundry agent registration via the APIM gateway connection.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('APIM SKU name')
param skuName string = 'BasicV2'

@description('Publisher name for APIM')
param publisherName string = 'KB Agent Team'

@description('Publisher email for APIM')
param publisherEmail string = 'noreply@example.com'

// ---------------------------------------------------------------------------
// API Management Service
// ---------------------------------------------------------------------------
resource apimService 'Microsoft.ApiManagement/service@2024-06-01-preview' = {
  name: 'apim-${baseName}'
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherName: publisherName
    publisherEmail: publisherEmail
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output apimName string = apimService.name
output apimGatewayUrl string = apimService.properties.gatewayUrl
output apimPrincipalId string = apimService.identity.principalId
output apimResourceId string = apimService.id
