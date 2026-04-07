def message_handler(message):
    # Constructing the prompt for ai_analyze
    prompt = "Iltimos, sizga yordam berishingiz uchun quyidagi ko'rsatmalarga rioya qiling: [your detailed instructions here]"
    result = ai_analyze(prompt)
    # Handle the result as required
    return result