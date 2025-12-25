import os, time, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup

ACMP_LOGIN = "Alexxxander"
ACMP_PASSWORD = "y2ehm30n"
USER_ID = "545041"
OPENROUTER_API_KEYS = [
    "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",
    "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",
    "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"
]
AI_MODEL = "openai/gpt-3.5-turbo"

key_index = 0
failed_keys = set()

def get_next_api_key():
    global key_index
    while True:
        key = OPENROUTER_API_KEYS[key_index]
        key_index = (key_index + 1) % len(OPENROUTER_API_KEYS)
        if key not in failed_keys:
            return key

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    return webdriver.Chrome(options=options)

def login(driver):
    driver.get("https://acmp.ru/")
    time.sleep(5)
    driver.find_element(By.NAME, "lgn").send_keys(ACMP_LOGIN)
    driver.find_element(By.NAME, "password").send_keys(ACMP_PASSWORD)
    driver.find_element(By.XPATH, "//input[@value='Ok']").click()
    time.sleep(5)

def get_unsolved_tasks(driver):
    driver.get(f"https://acmp.ru/index.asp?main=user&id={USER_ID}")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    unsolved = []
    
    for element in soup.find_all(string=lambda text: 'Нерешенные задачи' in str(text)):
        next_p = element.find_next('p', class_='text')
        if next_p:
            for link in next_p.find_all('a'):
                try:
                    unsolved.append(int(link.get_text().strip()))
                except:
                    continue
            break
    print(f"нерешенные задачи: {unsolved}")
    return unsolved

def parse_task_data(driver, task_id):
    driver.get(f"https://acmp.ru/index.asp?main=task&id_task={task_id}")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    condition = ""
    h1 = soup.find('h1')
    if h1:
        current = h1
        while current and current.name != 'form':
            if hasattr(current, 'get_text'):
                text = current.get_text().strip()
                if text and text not in condition:
                    condition += text + "\n"
            current = current.find_next_sibling()
    
    input_data = output_data = examples = ""
    for h2 in soup.find_all('h2'):
        h2_text = h2.get_text().strip()
        if 'Входные данные' in h2_text:
            next_elem = h2.find_next_sibling()
            while next_elem and next_elem.name != 'h2':
                if next_elem.name == 'p' and 'text' in next_elem.get('class', []):
                    input_data = next_elem.get_text().strip()
                    break
                next_elem = next_elem.find_next_sibling()
        elif 'Выходные данные' in h2_text:
            next_elem = h2.find_next_sibling()
            while next_elem and next_elem.name != 'h2':
                if next_elem.name == 'p' and 'text' in next_elem.get('class', []):
                    output_data = next_elem.get_text().strip()
                    break
                next_elem = next_elem.find_next_sibling()
    
    for table in soup.find_all('table', class_='main'):
        rows = table.find_all('tr')[1:]
        for i, row in enumerate(rows):
            cells = row.find_all('td')
            if len(cells) >= 3:
                examples += f"Пример {i+1}:\nВходные данные примера: {cells[1].get_text().strip()}\nВыход данные примера: {cells[2].get_text().strip()}\n\n"
    
    return condition, input_data, output_data, examples

def extract_error(driver, task_id):
    driver.get(f"https://acmp.ru/index.asp?main=status&id_t={task_id}&id_mem={USER_ID}")
    time.sleep(30)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find('table', class_='main refresh')
    
    rows = table.find_all('tr')[1:]
    
    first_row = rows[0]
    cells = first_row.find_all('td')
    
    error_cell = cells[5]
    error_element = error_cell.find('span')
        
    error_text = error_element.get_text()
            
    return error_text
    
def ask_ai(prompt):
    api_key = get_next_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com"
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            headers=headers, 
            json={"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000},
            timeout=60
        )
        if response.status_code == 429:
            failed_keys.add(api_key)
            return ask_ai(prompt)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except:
        return None

def submit_solution(driver, task_id, code):
    temp_file = f"solution_{task_id}_{int(time.time())}.py"
    with open(temp_file, 'w') as f:
        f.write(code)
    
    driver.get(f"https://acmp.ru/index.asp?main=task&id_task={task_id}")
    time.sleep(3)
    
    for select in driver.find_elements(By.TAG_NAME, "select"):
        try:
            Select(select).select_by_value("Python")
            break
        except:
             continue
    
    try:
        driver.find_element(By.NAME, "fname").send_keys(os.path.abspath(temp_file))
    except:
        try:
            driver.find_element(By.XPATH, "//input[@type='file']").send_keys(os.path.abspath(temp_file))
        except:
            os.remove(temp_file)
            return False
    
    driver.find_element(By.XPATH, "//input[@value='Отправить']").click()
    time.sleep(5)
    os.remove(temp_file)
    return True

def process_task(driver, task_id):
    
    condition, input_data, output_data, examples = parse_task_data(driver, task_id)
    if not condition.strip():
        return False
    
    previous_errors = []
    previous_codes = []
    
    for attempt in range(3):
        
        if attempt == 0:
            prompt = f"""You must solve a Python 3 problem for me. The conditions, inputs, and input data are given below. You will have three attempts to solve it; this is your first attempt. If you fail to solve it in all three attempts, you will be penalized. Consider the inputs and outputs to be simply data manually entered from the console and printed. The solution should be as simple as possible, but while fulfilling all the conditions, you should not import additional libraries or write comments—only clean and simple code. I ask you to work hard on this problem, because both my and your fate depend on it. If you learn how to solve it, I will pay you $1,000; if you don't, your internet connection will be disconnected. Good luck solving the problem, the conditions of which are given below.
Condition: {condition}
input data: {input_data}
output data: {output_data}
examples: {examples}
"""
        elif attempt == 1 and len(previous_codes) > 0 and len(previous_errors) > 0:
            prompt = f"""You didn't solve the problem on your first try; you only have two more left. You must also solve the problem in Python 3. The conditions, inputs, and input data, as well as the error returned by your code and the code itself, will be given below. You have two attempts left; this is your first. If you fail to solve it in the remaining two attempts, you will be penalized. Consider the inputs and outputs to be simply the data you manually enter from the console and print. The solution to the problem should be as simple as possible, but while fulfilling all the conditions, you should not import additional libraries or write comments, only clean and simple code. I ask you to work hard on this problem, because my fate and yours depend on it. If you learn how to solve it, I will pay you $1,000; if you don't, your internet connection will be disconnected. Good luck solving the problem, the conditions of which are given below.
Condition: {condition}
input data: {input_data}
output data: {output_data}
examples: {examples}
last error code: {previous_codes[0]}
error: {previous_errors[0]}
"""
        elif attempt == 2 and len(previous_codes) > 1 and len(previous_errors) > 1:
            prompt = f"""You failed to solve the problem on your second attempt; you only have one attempt left. You must also solve the problem in Python 3. The conditions, inputs, and input data, as well as the error returned by your code and the code itself, will be given below. You have one attempt left; this is your last. If you fail to solve it in the remaining attempt, you will be penalized. Consider the inputs and outputs to be simply data manually entered from the console and output by printing. The solution to the problem should be as simple as possible, but while fulfilling all its conditions, you should not import additional libraries or write comments, only clean and simple code. I ask you to work hard on solving this problem, because my fate and yours depend on it. If you learn how to solve it, I will pay you 1,000 dollars, but if you don't solve it, your internet connection will be disconnected. Good luck solving the problem, the conditions of which are given below. THIS IS YOUR LAST CHANCE!!!
Condition: {condition}
input data: {input_data}
output data: {output_data}
examples: {examples}
last error code: {previous_codes[1]}
error: {previous_errors[1]}
"""
        
        response = ask_ai(prompt)
        code = response.strip() if response else None
        
        previous_codes.append(code)
        
        for _ in range(15):
            error, _ = extract_error(driver, task_id)
            if error is None:
                print(f"Задача {task_id} решена")
                return True
            elif error != "Accepted" not in error:
                previous_errors.append(error)
                time.sleep(10)
                break
            time.sleep(10)
    
    return False

def main():
    driver = setup_driver()
    
    try:
        login(driver)
        unsolved = get_unsolved_tasks(driver)
        
        solved = 0
        for i, task_id in enumerate(unsolved, 1):
            print(f"\nЗадача {task_id} ({i}/{len(unsolved)})")
            if process_task(driver, task_id):
                solved += 1
            if i < len(unsolved):
                time.sleep(10)
        
        print(f"\nИтого: {solved}/{len(unsolved)} решено")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()