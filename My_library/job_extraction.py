import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

# from tabulate import tabulate


def extract_job_detail(job_url):
    try:
        # response = requests.get(url, headers=headers)
        job_response = requests.get(job_url, timeout=10)
        if job_response.status_code == 200:
            _soup = BeautifulSoup(job_response.text, 'html.parser')

            form = _soup.find("form", {"name": "jobForm"})

            if not form:
                print("Form named 'jobForm' not found.")
            else:
                # Extract field names and corresponding data
                # fields = {}
                
                data = {}
                job_rows = form.find_all("tr")  # Assuming the form uses <tr> for rows
                for row in job_rows:
                    columns = row.find_all("td")  # Assuming the form uses <td> for columns
                    if len(columns) == 2:  # Two columns: field name and data
                        field_name = columns[0].text.strip()
                        field_data = columns[1].text.strip()
                        if field_name and field_name not in ['Monthly Salary Range HK$', 'Payroll', 'Apply To', 'Direct Line', 'Employer Business']:
                            # fields[field_name] = field_data                           
                                data[field_name] = field_data
                                
                                if field_name == 'Duties':
                                	data['B/D'] = extract_bd(field_data)
                                if  field_name == 'Job Title/ Category' :
                                	data['Title'] = extract_title(field_data)                                                        
                # Print the extracted data
                # for field_name, field_data in fields.items():
                #     print(f"{field_name}: {field_data}")
                # print(json.dumps(fields, indent=2))
                
                return data

        else:
            print(f"Failed to fetch page. Status code: {response.status_code}")

    except Exception as e:
        print(f"Error: {e}")


def extract_title(text):
    keyword_index = text.find('(')

    if keyword_index != -1:
        extracted_string = text[:keyword_index].strip()

        if extracted_string:
            abbreviation = ''.join(word[0] for word in extracted_string.split())
            return abbreviation
        else:
            return None
    else:
        return None

def extract_bd(text):
    try:
        keyword_index_1 = text.index('serve the')
    except ValueError:
        return None

    match = re.search(r'(\n|\r)', text)
    if match:
        keyword_index_2 = match.start()
        return text[keyword_index_1 + len('serve the '): keyword_index_2].strip().replace(';', '')

    return None

url = "https://infotech.com.hk/itjs/job/fe-search.do?method=feList&sortByField=jjm_activedate&sortByOrder=DESC"

search_keys = set()
try:
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Example: Extract all links on the page
        links = soup.find_all('a')
        for link in links:
            if 'Contract' in link.text and 'Bid' in link.text:
                sub_url = link.get('href')
                key_pos = sub_url.index('jjKey=')
                if key_pos >= 0:
                    search_keys.add(sub_url[key_pos + len('jjKey='):])
                # print(f"Link: {link.text.strip()} -> {sub_url}")
         
        file_path = 'job_detail.xlsx'
        sheet_name = 'Details'
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print("Start job detail extraction")
        base_url = "https://www.infotech.com.hk/itjs/job/fe-view.do?method=feView&jjKey="

        rows = []
        start = time.time()

        for key in search_keys - set(df['Job Key No'].astype(str)):
            job_start = time.time()
            job = extract_job_detail(base_url + key)
            job_end = time.time()
            if job:
                rows.append(job)
            print(f"Extract job {key} in {round(job_end - job_start, 2)} seconds.")

        end = time.time()
        print(f"Total extraction time: {round(end - start, 2)} seconds.")
        if rows:
        	new_rows = pd.DataFrame(rows)
        	df = pd.concat([df, new_rows], ignore_index=True)
        	with pd.ExcelWriter(file_path, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
        		df.to_excel(writer, sheet_name=sheet_name, index=Flase)
        else:
        	print('no record found')

    else:
        print(f"Failed to fetch page. Status code: {response.status_code}")

except Exception as e:
    print(f"Error: {e}")