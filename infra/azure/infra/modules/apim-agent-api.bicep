// ---------------------------------------------------------------------------
// Module: apim-agent-api.bicep
// Defines the KB Agent API on an existing APIM instance: backend, API
// definition, policy (pass-through proxy), and operations.
// ---------------------------------------------------------------------------

@description('Name of the existing APIM resource')
param apimName string

@description('Agent external HTTPS URL (e.g., https://agent-xxx.azurecontainerapps.io)')
param agentExternalUrl string

// ---------------------------------------------------------------------------
// Reference existing APIM
// ---------------------------------------------------------------------------
resource apim 'Microsoft.ApiManagement/service@2024-06-01-preview' existing = {
  name: apimName
}

// ---------------------------------------------------------------------------
// Backend: KB Agent Container App
// ---------------------------------------------------------------------------
resource agentBackend 'Microsoft.ApiManagement/service/backends@2024-06-01-preview' = {
  parent: apim
  name: 'kb-agent-backend'
  properties: {
    url: agentExternalUrl
    protocol: 'http'
  }
}

// ---------------------------------------------------------------------------
// API Definition: KB Agent API
// ---------------------------------------------------------------------------
resource agentApi 'Microsoft.ApiManagement/service/apis@2024-06-01-preview' = {
  parent: apim
  name: 'kb-agent-api'
  properties: {
    displayName: 'KB Agent API'
    path: ''
    protocols: [
      'https'
    ]
    subscriptionRequired: false
    serviceUrl: agentExternalUrl
  }
}

// ---------------------------------------------------------------------------
// API Policy: pass-through proxy via backend
// ---------------------------------------------------------------------------
resource agentApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-06-01-preview' = {
  parent: agentApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><base /><set-backend-service backend-id="kb-agent-backend" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
  dependsOn: [
    agentBackend
  ]
}

// ---------------------------------------------------------------------------
// Operations
// ---------------------------------------------------------------------------
resource opPostResponses 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: agentApi
  name: 'post-responses'
  properties: {
    displayName: 'Process message'
    method: 'POST'
    urlTemplate: '/responses'
  }
}

resource opPostAgUi 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: agentApi
  name: 'post-ag-ui'
  properties: {
    displayName: 'AG-UI stream'
    method: 'POST'
    urlTemplate: '/ag-ui'
  }
}

resource opGetLiveness 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: agentApi
  name: 'get-liveness'
  properties: {
    displayName: 'Liveness probe'
    method: 'GET'
    urlTemplate: '/liveness'
  }
}

resource opGetReadiness 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: agentApi
  name: 'get-readiness'
  properties: {
    displayName: 'Readiness probe'
    method: 'GET'
    urlTemplate: '/readiness'
  }
}

resource opGetCitationLookup 'Microsoft.ApiManagement/service/apis/operations@2024-06-01-preview' = {
  parent: agentApi
  name: 'get-citation-lookup'
  properties: {
    displayName: 'Transcript-scoped citation lookup'
    method: 'GET'
    urlTemplate: '/citations/{threadId}/{toolCallId}/{refNumber}'
    templateParameters: [
      {
        name: 'threadId'
        required: true
        type: 'string'
      }
      {
        name: 'toolCallId'
        required: true
        type: 'string'
      }
      {
        name: 'refNumber'
        required: true
        type: 'string'
      }
    ]
  }
}
