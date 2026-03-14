import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as opensearch from 'aws-cdk-lib/aws-opensearchserverless';
import * as batch from 'aws-cdk-lib/aws-batch';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class OncoAIStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 Bucket for data storage
    const dataBucket = new s3.Bucket(this, 'OncoDataBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30)
            }
          ]
        }
      ]
    });

    // DynamoDB for campaign metadata
    const campaignsTable = new dynamodb.Table(this, 'OncoCampaigns', {
      partitionKey: { name: 'campaignId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });
    
    campaignsTable.addGlobalSecondaryIndex({
      indexName: 'StatusIndex',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING }
    });

    // OpenSearch Serverless for Memory Bank
    const memoryCollection = new opensearch.CfnCollection(this, 'MemoryBank', {
      name: 'oncoai-memory',
      type: 'VECTORSEARCH',
      description: 'Periodic memory storage for failed predictions'
    });

    // Lambda Functions
    const lambdaRole = new iam.Role(this, 'LambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonS3FullAccess'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonDynamoDBFullAccess')
      ]
    });

    const orchestratorFn = new lambda.Function(this, 'OrchestratorFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../backend/lambda/orchestrator'),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      environment: {
        BUCKET_NAME: dataBucket.bucketName,
        CAMPAIGNS_TABLE: campaignsTable.tableName
      }
    });

    const memoryStoreFn = new lambda.Function(this, 'MemoryStoreFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../backend/lambda/memory_store'),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(1),
      memorySize: 512,
      environment: {
        OPENSEARCH_ENDPOINT: memoryCollection.attrCollectionEndpoint
      }
    });

    const generatorFn = new lambda.Function(this, 'GeneratorFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../backend/lambda/generator'),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 3008, // Max for Lambda
      environment: {
        MODEL_PATH: 's3://oncoai-models/generative_model.pth'
      }
    });

    const predictorFn = new lambda.Function(this, 'PredictorFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../backend/lambda/predictor'),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(5),
      memorySize: 3008,
      environment: {
        MODEL_PATH: 's3://oncoai-models/gnn_predictor.pth'
      }
    });

    const toxicityCheckerFn = new lambda.Function(this, 'ToxicityCheckerFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../backend/lambda/toxicity_checker'),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(1),
      memorySize: 1024
    });

    // Batch Environment for Docking
    const vpc = new ec2.Vpc(this, 'OncoVPC', { maxAzs: 2 });
    
    const batchQueue = new batch.JobQueue(this, 'DockingQueue', {
      priority: 1
    });

    const batchComputeEnv = new batch.ManagedEc2EcsComputeEnvironment(this, 'DockingComputeEnv', {
      vpc,
      computeResources: {
        instanceTypes: [
          ec2.InstanceType.of(ec2.InstanceClass.C5, ec2.InstanceSize.XLARGE),
          ec2.InstanceType.of(ec2.InstanceClass.G4DN, ec2.InstanceSize.XLARGE)
        ],
        maxvCpus: 64,
        spot: true
      }
    });
    
    batchQueue.addComputeEnvironment(batchComputeEnv, 1);

    const dockingJobDef = new batch.EcsJobDefinition(this, 'DockingJobDef', {
      container: {
        image: ecs.ContainerImage.fromAsset('../docker/docking'),
        memory: cdk.Size.gibibytes(8),
        vcpus: 4,
        environment: {
          BUCKET_NAME: dataBucket.bucketName
        }
      }
    });

    // Step Functions Workflow
    const generateMolecules = new tasks.LambdaInvoke(this, 'Generate Molecules', {
      lambdaFunction: generatorFn,
      outputPath: '$.Payload'
    });

    const recallMemory = new tasks.LambdaInvoke(this, 'Recall Memory', {
      lambdaFunction: memoryStoreFn,
      payload: sfn.TaskInput.fromObject({
        action: 'query',
        candidates: sfn.JsonPath.stringAt('$.generated_molecules'),
        protein: sfn.JsonPath.stringAt('$.protein_target')
      }),
      outputPath: '$.Payload'
    });

    const predictBinding = new tasks.LambdaInvoke(this, 'Predict Binding', {
      lambdaFunction: predictorFn,
      payload: sfn.TaskInput.fromObject({
        molecules: sfn.JsonPath.stringAt('$.molecules'),
        protein: sfn.JsonPath.stringAt('$.protein_target'),
        memory_context: sfn.JsonPath.stringAt('$.memory_context')
      }),
      outputPath: '$.Payload'
    });

    const checkToxicity = new tasks.LambdaInvoke(this, 'Check Toxicity', {
      lambdaFunction: toxicityCheckerFn,
      payload: sfn.TaskInput.fromObject({
        molecules: sfn.JsonPath.stringAt('$.top_candidates')
      }),
      outputPath: '$.Payload'
    });

    const runDocking = new tasks.BatchSubmitJob(this, 'Run Docking Validation', {
      jobDefinitionArn: dockingJobDef.jobDefinitionArn,
      jobQueueArn: batchQueue.jobQueueArn,
      jobName: 'docking-validation',
      payload: sfn.TaskInput.fromObject({
        molecules: sfn.JsonPath.stringAt('$.safe_molecules'),
        protein: sfn.JsonPath.stringAt('$.protein_target')
      })
    });

    const updateMemory = new tasks.LambdaInvoke(this, 'Update Memory', {
      lambdaFunction: memoryStoreFn,
      payload: sfn.TaskInput.fromObject({
        action: 'store',
        predictions: sfn.JsonPath.stringAt('$.predictions'),
        validation: sfn.JsonPath.stringAt('$.docking_results')
      })
    });

    const notifyComplete = new tasks.LambdaInvoke(this, 'Notify Completion', {
      lambdaFunction: orchestratorFn,
      payload: sfn.TaskInput.fromObject({
        action: 'notify',
        results: sfn.JsonPath.stringAt('$.docking_results')
      })
    });

    // Define workflow
    const workflow = generateMolecules
      .next(recallMemory)
      .next(predictBinding)
      .next(checkToxicity)
      .next(runDocking)
      .next(updateMemory)
      .next(notifyComplete);

    const stateMachine = new sfn.StateMachine(this, 'OncoAIWorkflow', {
      definition: workflow,
      timeout: cdk.Duration.hours(2)
    });

    // API Gateway
    const api = new apigateway.RestApi(this, 'OncoAIAPI', {
      restApiName: 'OncoAI Service',
      description: 'API for OncoAI cancer drug discovery platform'
    });

    const campaignResource = api.root.addResource('campaign');
    campaignResource.addMethod('POST', new apigateway.LambdaIntegration(orchestratorFn));
    
    const campaignIdResource = campaignResource.addResource('{campaignId}');
    campaignIdResource.addMethod('GET', new apigateway.LambdaIntegration(orchestratorFn));

    // Outputs
    new cdk.CfnOutput(this, 'APIEndpoint', { value: api.url });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
    new cdk.CfnOutput(this, 'DataBucket', { value: dataBucket.bucketName });
  }
}