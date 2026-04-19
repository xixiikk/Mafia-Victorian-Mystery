def turn_task_into_prompt(task, message_history):
    history_text = "\n".join(message_history)
    return f"{task}\n\nChat history:\n{history_text}"