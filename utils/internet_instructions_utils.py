from src.locale_manager import locale_manager as lm

def get_web_search_instruction(result):
    return lm.get('web_search_instruction').format(result=result)

def get_image_search_instruction(result):
    return lm.get('image_search_instruction').format(result=result)

def get_video_search_instruction(result):
    return lm.get('video_search_instruction').format(result=result)