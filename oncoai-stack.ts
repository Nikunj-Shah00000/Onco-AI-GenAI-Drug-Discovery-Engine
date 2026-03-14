#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { OncoAIStack } from '../lib/oncoai-stack';

const app = new cdk.App();
new OncoAIStack(app, 'OncoAIStack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1'
  },
});