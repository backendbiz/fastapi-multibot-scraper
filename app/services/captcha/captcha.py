import base64
import os
import capsolver
import requests
import time
from app.core.config import settings

twocaptcha_api = os.getenv("twocaptcha_api")
capsolver_api = os.getenv("capsolver_api")

def solving_captcha(driver, wait, img_element):
    answer = False
    i = 0
    while not answer and i < 2:
        screenshot_data = img_element.screenshot_as_png

        result, answer , restart_requiremnent_check= capsolver_request(screenshot_data)
        if not answer:
            result, answer , restart_requiremnent_check = twocaptcha_request(img_element)
            print(result, answer , restart_requiremnent_check)
            if not answer:
                img_element.click()
                i+=1
            else:
                break
        elif answer == True:
            break 
    print("0result")
    print(result," " ,restart_requiremnent_check)
    #os.remove(img_path)
    return result ,restart_requiremnent_check  # if resetart_requiremnet= true must restart tabs

def capsolver_request(screenshot_data):
    capsolver.api_key = capsolver_api
    print(capsolver_api)
    encoded_string = base64.b64encode(screenshot_data).decode("utf-8")
    result = capsolver.solve({
        "type": "ImageToTextTask",
        "module": "common",
        "body": encoded_string,
        "case": False
    })
    # print(result, len(result["answers"][0]))
    # print((result.get("text") is not None and not result.get("text").isdigit()))
    # print((result.get("answers") is not None and not result.get("answers")[0].isdigit()))
    try:
        ##### second return statement is for unsolvable captcha cuz of distortion
        if (result.get("text") is not None and not result.get("text").isdigit()) or (result.get("answers") is not None and not result.get("answers")[0].isdigit()):
            print("contains invalid captcha format:", result)
            return result, False , True
        elif (result.get("confidence") is not None and result["confidence"] > 0.8) or (result.get("answers") is not None and len(result["answers"][0]) >= 4):  # success
            
            if result.get('text'):
                print("Success:", result["text"])
                return result["text"], True , False
            elif result.get('answers'):
                print("Successss:", result["answers"][0])
                return result["answers"][0], True , False
        else:  # error
            print("Error:", result)
            return result, False , False
    except Exception as e:
        print(e)
        return result, False , False
    
def twocaptcha_request(img_element):
    API_KEY = twocaptcha_api
    print(twocaptcha_api)
    screenshot_data = img_element.screenshot_as_png
    img_path =  "captcha_screenshot.png"
        
    with open(img_path, 'wb') as file:
        file.write(screenshot_data)
        
     # The CAPTCHA image file
    captcha_file = "captcha_screenshot.png"
    try:
        # Send the CAPTCHA to the 2Captcha service
        with open(captcha_file, 'rb') as f:
            response = requests.post('https://2captcha.com/in.php', files={'file': f}, data={'key': API_KEY, 'method': 'post'})
        task_id = response.text.split('|')[1]
        timeout = 0
        # Start a cycle that checks if your task is completed
        while timeout < 3:
            response = requests.get(f'https://2captcha.com/res.php?key={API_KEY}&action=get&id={task_id}')
            if response.text == 'CAPCHA_NOT_READY':
                time.sleep(5)
                timeout += 1
                continue
            else:
                captcha_text = response.text.split('|')[1]
                break

        print(f'The CAPTCHA text is: {captcha_text}')
    except:
        captcha_text = "error"
    
    try:
        os.remove(captcha_file)
    except:
        pass
    #print(result)
    try:
        ##### second return statement is for unsolvable captcha cuz of distortion
        if not captcha_text.isdigit():
            print("contains invalid captcha format:", captcha_text)
            return captcha_text, False , True
        elif captcha_text.isdigit():
            print("captch sucessfull:", captcha_text)
            return captcha_text, True , False
        else:  # error
            print("Error:", captcha_text)
            return captcha_text, False , False
    except:
        return captcha_text, False , False
    