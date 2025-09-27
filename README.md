# MindSpire: A Mental Health Support Platform for Students

MindSpire is a comprehensive prototype for a student mental health support system. It combines a student-facing dashboard with an anonymous peer support forum, a counsellor booking system, and a crisis escalation service powered by a chatbot and Twilio.

## ✨ Features

* **Student Dashboard (`mental.py`):** A central hub for students to access resources, check their mood, book appointments, and chat with a support bot.
* **Admin Dashboard (`Admin.py`):** A secure panel for counsellors/admins to manage bookings, set availability, view analytics on platform usage, and monitor crisis escalations.
* **Peer Support Forum (`peer_chat.py`):** An anonymous, real-time chat forum with different channels for students to connect and support each other. Includes moderation tools and keyword-based crisis detection.
* **Crisis Escalation (`escalate.py` & Botpress):** A robust webhook system that allows a chatbot (like Botpress) to trigger a direct phone call to a counsellor via Twilio when a user is in crisis.

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend Webhooks:** Flask
* **Real-time Calling/SMS:** Twilio
* **Database:** Firebase Realtime Database (for chat/escalations) & local JSON file (for bookings/availability)
* **Chatbot:** Botpress (integrated via webhook)
* **Data Analysis:** Pandas

---

## 🚀 Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

* Python 3.8+
* A Twilio account with a phone number
* A Google Firebase Realtime Database
* A Botpress account and a configured bot
* `ngrok` for local testing of webhooks

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/mindspire.git](https://github.com/your-username/mindspire.git)
    cd mindspire
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your secrets:**
    * Make a copy of the example environment file:
        ```bash
        cp .env.example .env
        ```
    * Open the `.env` file and fill in your actual secret keys and configuration details from Firebase, Twilio, and Botpress.

### Running the Application

This project has multiple services. You will need to run them in separate terminal windows.

1.  **Run the Student Dashboard:**
    ```bash
    streamlit run mental.py
    ```

2.  **Run the Admin Dashboard:**
    ```bash
    streamlit run Admin.py
    ```

3.  **Run the Escalation Webhook:**
    ```bash
    python escalate.py
    ```

4.  **Expose the Webhook with `ngrok`:**
    * The `escalate.py` script runs on port 8000. To make it accessible to Botpress, run:
        ```bash
        ngrok http 8000
        ```
    * Copy the HTTPS Forwarding URL from ngrok and set it as the `ESCALATE_WEBHOOK_URL` in your `.env` file and in the Botpress Cloud environment variables.
