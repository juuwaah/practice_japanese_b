# Google OAuth Setup Instructions

## Google Cloud Console Setup

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable Google+ API**
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API" and enable it

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Application type: "Web application"
   - Name: "JLPT Practice App"
   - Authorized redirect URIs:
     - http://localhost:5000/auth/google/authorized
     - https://yourdomain.com/auth/google/authorized (for production)

4. **Get Client ID and Secret**
   - Copy the Client ID and Client Secret

## Environment Variables

Add these to your `.env` file:

```
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
```

## Database Migration

Run these commands to update the database:

```bash
flask db init
flask db migrate -m "Add Google OAuth support"
flask db upgrade
```

## Features Implemented

- **Google Login**: Users can sign in with their Google account
- **Patreon Login**: Existing Patreon integration maintained
- **Guest Access**: Users can browse without logging in
- **Admin Account**: suhdudebac@gmail.com automatically gets admin privileges
- **Feedback Restriction**: Only logged-in users (Google/Patreon) can send feedback

## User Flow

1. **Guest Users**: Can browse most content, limited features
2. **Google Users**: Full access to regular features
3. **Patreon Users**: Access to premium features
4. **Admin**: suhdudebac@gmail.com gets admin dashboard access