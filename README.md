# Langgraph Receptionist Agent

This is a repo containing a simple receptionist agent that can book and cancel appointments using Google Calendar. The idea of the setup is quite simple:

1. First create a GCP project
- Open the Google Cloud Console: https://console.cloud.google.com/
- Sign in with your Google account.
- In the project selector (at the top), click on 'Create project'.
- Assign a name (e.g. 'Streamlit Calendar Desktop') and create the project.

2. Configure consent screen
- In the left sidebar, click on 'APIs & Services' > 'OAuth consent screen'.
- Select 'External' as the user type.
- Fill in the required information (e.g. app name, user support email, developer contact information).
- Add the following scopes:
    - https://www.googleapis.com/auth/userinfo.email
    - https://www.googleapis.com/auth/calendar
- Save the consent screen.

3. Create desktop app credentials
- In the left sidebar, click on 'APIs & Services' > 'Credentials'.
- Click on 'Create Credentials' > 'Desktop app'.
- Name the app (e.g. 'Streamlit Calendar Desktop') and create it.
- Download the JSON file and save it as 'credentials.json' in the root directory of this repo.

4. Add test users for a dev environment
- In the left sidebar, click on 'APIs & Services' > 'OAuth consent screen'.
- Click on 'Test users'.
- Add the email address of the user you want to test with.

5. Install dependencies
- Run `pip install -r requirements.txt`

6. Run the app
- If token.json exist, it will be used. Otherwise, it will be created.
- Run `streamlit run streamlit_app.py`


# Repo content 
```bash
-LangGraphReceptionist
    - caller_agent.py
    - tools.py
    - streamlit_app.py
    - requirements.txt
    - credentials.json
    - token.json # created by the app
    - .env
    - README.md
```

# Dive into main files


> [!NOTE]
> tools.py contains the tools that are used by the caller agent.

The main functions include:
- `init_services()`: Initializes the services.
- `get_current_user_email()`: Returns the email of the current user.
- `logout()`: Logs out the user.
- `get_next_available_appointment()`: Returns the next available appointment.
- `book_appointment()`: Books an appointment.
- `cancel_appointment()`: Cancels an appointment.
- `get_all_available_appointments()`: Returns all available appointments.
- `list_upcoming_appointments(max_results: int = 10)`: Lists upcoming appointments.

> [!IMPORTANT]
> Most of the functions are tools therefor they are decorated with `@tool`. The only exception is `list_upcoming_appointments`.

> [!NOTE]
> caller_agent.py contains the main logic of the caller agent.

The main functions include:
- `receive_message_from_caller(message)`: Receives a message from the caller and passes it to the caller app.
- `should_continue_caller(state: MessagesState)`: Returns 'continue' if the caller should continue calling tools, otherwise returns 'end'.
- `call_caller_model(state: MessagesState)`: Calls the caller model and generates a response.
- `tool_node`: A tool node that is used to invoke tools.
- `caller_workflow`: A state graph that represents the workflow of the caller agent.
- `caller_app`: The compiled caller app.

> [!NOTE]
> streamlit_app.py contains the main logic of the streamlit app.

This is a basic streamlit app that allows the user to interact with the caller agent.
