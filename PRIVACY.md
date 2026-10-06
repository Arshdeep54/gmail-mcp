# Privacy Policy

gmail-mcp-server is self-hosted, single-tenant software: you run your own instance on your
own infrastructure, using your own Google Cloud project and OAuth credentials.

- Your Gmail data and OAuth tokens are read by the Gmail API and processed only on the
  machine you deploy this server on. Nothing is sent to the developer or any third party.
- No analytics, telemetry, or usage data is collected by this project.
- The server requests `gmail.readonly` and `gmail.compose` scopes only: it can read mail
  and create drafts, and cannot send mail or delete anything on your behalf.
- Your OAuth refresh token is stored locally (`secrets/token.json` by default) on your own
  server and never leaves it.

Since you operate the only instance of this software with access to your account, you are
both the data controller and the data processor. See the [source code](https://github.com/Arshdeep54/gmail-mcp)
for exactly what the server does with your data.
