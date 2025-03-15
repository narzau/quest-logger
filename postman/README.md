# Quest Logger API Postman Collections

This directory contains Postman collections and environments for testing the Quest Logger API. These collections provide pre-configured requests for all available API endpoints.

## Collections

- **QuestLogger_Notes_API.json** - Collection for Notes API endpoints
- **QuestLogger_Subscription_API.json** - Collection for Subscription API endpoints

## Environments

- **QuestLogger_Local.json** - Environment variables for local development

## How to Use

1. Import the collections and environment into Postman:

   - Open Postman
   - Click "Import" button
   - Select the collection JSON files and environment JSON file

2. Set up your environment:

   - Click on the environment dropdown in the top-right corner
   - Select "QuestLogger Local"
   - Edit the environment variables:
     - The `base_url` is preset to `http://localhost:8000`
     - Set your `access_token` after authenticating
     - You can set `note_id` and `share_id` as needed during testing

3. Get an access token:

   - Use the login endpoint (not included in these collections)
   - Copy the returned token
   - Update the `access_token` variable in your environment

4. Start making requests:
   - Select a request from one of the collections
   - Review and modify the request body if needed
   - Click "Send" to make the request

## Notes API

The Notes API collection includes endpoints for:

- Creating, reading, updating, and deleting notes
- Managing folders and tags
- Sharing notes
- Creating and processing voice notes
- Exporting notes in different formats

## Subscription API

The Subscription API collection includes endpoints for:

- Getting subscription status and pricing
- Managing subscription (subscribe, unsubscribe)
- Payment management
- Billing cycle changes
- Promotional codes
- Checkout sessions
- Trial notifications

## Variables

These collections use the following variables:

- `base_url` - The base URL of the API (e.g., http://localhost:8000)
- `access_token` - JWT token for authentication
- `note_id` - ID of a note to operate on
- `share_id` - Share ID for accessing shared notes

Remember to update these variables as needed for your testing.
