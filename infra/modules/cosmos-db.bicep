// ---------------------------------------------------------------------------
// Module: cosmos-db.bicep
// Deploys Azure Cosmos DB (NoSQL API, serverless) for agent session persistence.
// ---------------------------------------------------------------------------

@description('Azure region for resources')
param location string

@description('Base name used for resource naming')
param baseName string

@description('Tags to apply to all resources')
param tags object = {}

@description('Database name')
param databaseName string = 'kb-agent'


// ---------------------------------------------------------------------------
// Cosmos DB Account (NoSQL API, Serverless)
// ---------------------------------------------------------------------------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-${baseName}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      { name: 'EnableServerless' }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    disableLocalAuth: true
    minimalTlsVersion: 'Tls12'
    publicNetworkAccess: 'Enabled'
    // Allow traffic from Azure services (e.g. Container Apps without VNet integration).
    // Safe because disableLocalAuth=true ensures only RBAC-authenticated identities can access data.
    ipRules: [
      { ipAddressOrRange: '0.0.0.0' } // "Accept connections from within Azure datacenters"
    ]
  }
}

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// ---------------------------------------------------------------------------
// Container: agent-sessions (partition key: /id)
// ---------------------------------------------------------------------------
resource agentSessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'agent-sessions'
  properties: {
    resource: {
      id: 'agent-sessions'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/state/*' }
          { path: '/"_etag"/?' }
        ]
      }
      defaultTtl: -1 // No TTL — sessions persist indefinitely
    }
  }
}

// ---------------------------------------------------------------------------
// Container: conversations (partition key: /userId)
// Web app owns — lightweight metadata for sidebar
// ---------------------------------------------------------------------------
resource conversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/"_etag"/?' }
        ]
      }
      defaultTtl: -1
    }
  }
}

// ---------------------------------------------------------------------------
// Container: messages (partition key: /conversationId)
// Web app owns — one doc per message, insert-only
// ---------------------------------------------------------------------------
resource messagesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'messages'
  properties: {
    resource: {
      id: 'messages'
      partitionKey: {
        paths: ['/conversationId']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/content/*' }
          { path: '/"_etag"/?' }
        ]
      }
      defaultTtl: -1
    }
  }
}

// ---------------------------------------------------------------------------
// Container: references (partition key: /conversationId)
// Web app owns — one doc per chunk reference, point reads
// ---------------------------------------------------------------------------
resource referencesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'references'
  properties: {
    resource: {
      id: 'references'
      partitionKey: {
        paths: ['/conversationId']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/content/*' }
          { path: '/"_etag"/?' }
        ]
      }
      defaultTtl: -1
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output cosmosAccountId string = cosmosAccount.id
output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosDatabaseName string = database.name
