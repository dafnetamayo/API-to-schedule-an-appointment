import streamlit as st
from caller_agent import CONVERSATION, receive_message_from_caller
from tools import list_upcoming_appointments, logout
from langchain_core.messages import HumanMessage

st.set_page_config(layout="wide")

def submit_message():
    receive_message_from_caller(st.session_state["message"])

col1, col2 = st.columns(2)

with col1:
    st.subheader("Appointment Manager")
    for message in CONVERSATION:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.write(message.content)
        else:
            with st.chat_message("assistant"):
                st.write(message.content)
    st.chat_input("Escribe tu mensaje...", on_submit=submit_message, key="message")

with col2:
    st.header("Próximas citas")
    # Botón para cerrar sesión
    if st.button("🔒 Cerrar sesión"):
        msg = logout()
        st.success(msg)
    # Listado de citas
    with st.spinner("Cargando desde Google Calendar..."):
        events = list_upcoming_appointments(10)  # evitando kwargs aquí
    if not events:
        st.info("No tienes citas próximas.")
    else:
        for ev in events:
            start = ev["start"].replace("T", " ").replace("Z", "")
            end   = ev["end"].replace("T", " ").replace("Z", "")
            st.markdown(f"- **{start} → {end}**: {ev['summary']}")
