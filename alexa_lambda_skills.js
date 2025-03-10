// alexa_lambda_skills.js
// -----------------------
// Daily Briefing Alexa Skill - AWS Lambda Function

const Alexa = require('ask-sdk-core');
const AWS = require('aws-sdk');
const axios = require('axios');

// Choose how you want to store/retrieve the briefing
const CONFIG = {
  storageType: 'file', // Options: 'file', 's3', 'dynamodb', 'api'
  s3Bucket: 'daily-briefing-data',
  s3Key: 'alexa_briefing.json',
  dynamoTable: 'DailyBriefings',
  apiEndpoint: process.env.API_ENDPOINT || 'https://your-api.example.com/daily-briefing'
};

// Setup AWS clients if needed
const s3 = new AWS.S3();
const dynamodb = new AWS.DynamoDB.DocumentClient();

// Helper function to get the latest briefing
const getBriefing = async () => {
  try {
    switch (CONFIG.storageType) {
      case 's3':
        // Fetch from S3
        const s3Params = {
          Bucket: CONFIG.s3Bucket,
          Key: CONFIG.s3Key
        };
        const s3Data = await s3.getObject(s3Params).promise();
        return JSON.parse(s3Data.Body.toString());
      
      case 'dynamodb':
        // Example approach: fetch the item by today's date
        const today = new Date().toISOString().split('T')[0];
        const queryParams = {
          TableName: CONFIG.dynamoTable,
          KeyConditionExpression: '#date = :date',
          ExpressionAttributeNames: { '#date': 'date' },
          ExpressionAttributeValues: { ':date': today },
          Limit: 1,
          ScanIndexForward: false
        };
        const dynamoData = await dynamodb.query(queryParams).promise();
        return dynamoData.Items[0];
      
      case 'api':
        // Fetch from an API endpoint
        const response = await axios.get(CONFIG.apiEndpoint);
        return response.data;
      
      case 'file':
      default:
        // For local testing only, you can mock data or read from a local file
        // In Lambda, there's no "local file" by default; you'd either upload it
        // or rely on a different approach
        return {
          date: new Date().toISOString().split('T')[0],
          briefing_text: "Here's your daily briefing. This is placeholder text if not using S3, DynamoDB, or an API.",
          last_updated: new Date().toISOString()
        };
    }
  } catch (error) {
    console.error('Error retrieving briefing:', error);
    throw error;
  }
};

// Handlers
const LaunchRequestHandler = {
  canHandle(handlerInput) {
    return Alexa.getRequestType(handlerInput.requestEnvelope) === 'LaunchRequest';
  },
  async handle(handlerInput) {
    try {
      const briefingData = await getBriefing();
      const speakOutput = briefingData.briefing_text || "I couldn't find a briefing for today. Please try again later.";
      
      return handlerInput.responseBuilder
        .speak(speakOutput)
        .reprompt('Would you like me to repeat that?')
        .withSimpleCard('Daily Briefing', 'Your daily briefing has been delivered.')
        .getResponse();
    } catch (error) {
      console.error('Error in LaunchRequestHandler:', error);
      return handlerInput.responseBuilder
        .speak("I'm sorry, I'm having trouble retrieving your daily briefing.")
        .getResponse();
    }
  }
};

const RepeatIntentHandler = {
  canHandle(handlerInput) {
    return Alexa.getRequestType(handlerInput.requestEnvelope) === 'IntentRequest'
      && Alexa.getIntentName(handlerInput.requestEnvelope) === 'AMAZON.RepeatIntent';
  },
  async handle(handlerInput) {
    try {
      const briefingData = await getBriefing();
      const speakOutput = briefingData.briefing_text || "I don't have a briefing to repeat.";
      
      return handlerInput.responseBuilder
        .speak(speakOutput)
        .reprompt('Would you like me to repeat that again?')
        .getResponse();
    } catch (error) {
      console.error('Error in RepeatIntentHandler:', error);
      return handlerInput.responseBuilder
        .speak("I'm having trouble repeating your briefing. Please try again later.")
        .getResponse();
    }
  }
};

const HelpIntentHandler = {
  canHandle(handlerInput) {
    return Alexa.getRequestType(handlerInput.requestEnvelope) === 'IntentRequest'
      && Alexa.getIntentName(handlerInput.requestEnvelope) === 'AMAZON.HelpIntent';
  },
  handle(handlerInput) {
    const speakOutput = 'This skill reads your personalized daily briefing with the latest research, tech news, and articles. Just say, "Alexa, open daily briefing" to hear it.';
    return handlerInput.responseBuilder
      .speak(speakOutput)
      .reprompt(speakOutput)
      .getResponse();
  }
};

const CancelAndStopIntentHandler = {
  canHandle(handlerInput) {
    return Alexa.getRequestType(handlerInput.requestEnvelope) === 'IntentRequest'
      && (
        Alexa.getIntentName(handlerInput.requestEnvelope) === 'AMAZON.CancelIntent' ||
        Alexa.getIntentName(handlerInput.requestEnvelope) === 'AMAZON.StopIntent'
      );
  },
  handle(handlerInput) {
    return handlerInput.responseBuilder
      .speak('Goodbye!')
      .getResponse();
  }
};

const SessionEndedRequestHandler = {
  canHandle(handlerInput) {
    return Alexa.getRequestType(handlerInput.requestEnvelope) === 'SessionEndedRequest';
  },
  handle(handlerInput) {
    console.log(`Session ended with reason: ${handlerInput.requestEnvelope.request.reason}`);
    return handlerInput.responseBuilder.getResponse();
  }
};

const ErrorHandler = {
  canHandle() {
    return true;
  },
  handle(handlerInput, error) {
    console.error('Error handling request:', error);
    const speakOutput = "Sorry, I had trouble processing that request. Please try again.";
    return handlerInput.responseBuilder
      .speak(speakOutput)
      .reprompt(speakOutput)
      .getResponse();
  }
};

// Export the Lambda handler
exports.handler = Alexa.SkillBuilders.custom()
  .addRequestHandlers(
    LaunchRequestHandler,
    RepeatIntentHandler,
    HelpIntentHandler,
    CancelAndStopIntentHandler,
    SessionEndedRequestHandler
  )
  .addErrorHandlers(ErrorHandler)
  .lambda();
