import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

from tabulate import tabulate


def extract_job_detail(url, with_header=False):
    try:
        # response = requests.get(url, headers=headers)
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            form = soup.find("form", {"name": "jobForm"})

            if not form:
                print("Form named 'jobForm' not found.")
            else:
                # Extract field names and corresponding data
                # fields = {}
                header = []
                data = []
                rows = form.find_all("tr")  # Assuming the form uses <tr> for rows
                for row in rows:
                    columns = row.find_all("td")  # Assuming the form uses <td> for columns
                    if len(columns) == 2:  # Two columns: field name and data
                        field_name = columns[0].text.strip()
                        field_data = columns[1].text.strip()
                        if field_name and field_name not in ['Monthly Salary Range HK$', 'Payroll', 'Apply To', 'Direct Line', 'Employer Business']:
                            # fields[field_name] = field_data
                            if with_header:
                                header.append(field_name)
                            data.append(field_data)

                # Print the extracted data
                # for field_name, field_data in fields.items():
                #     print(f"{field_name}: {field_data}")
                # print(json.dumps(fields, indent=2))
                if with_header:
                    return [header, data]
                else:
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

search_keys = []
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
                    search_keys.append(sub_url[key_pos + len('jjKey='):])
                # print(f"Link: {link.text.strip()} -> {sub_url}")

        print("Start job detail extraction")
        base_url = "https://www.infotech.com.hk/itjs/job/fe-view.do?method=feView&jjKey="

        start = time.time()
        job = extract_job_detail(base_url + search_keys[0], with_header=True)
        rows = [*job]
        end = time.time()
        print(f"Extract header and the first job in {round(end - start, 2)} seconds.")

        for index, key in enumerate(search_keys[1:]):
            job_start = time.time()
            job = extract_job_detail(base_url + key)
            job_end = time.time()
            if job:
                rows.append(job)
            print(f"Extract job {index + 1} of {len(search_keys)} in {round(job_end - job_start, 2)} seconds.")

        end = time.time()
        print(f"Total extraction time: {round(end - start, 2)} seconds.")

        df = pd.DataFrame(rows[1:], columns=rows[0])

        if 'Duties' in df.columns:
            df['B/D'] = df['Duties'].apply(extract_bd)
            df['Title'] = df['Job Title/ Category'].apply(extract_title)

        print(tabulate(df[['B/D', 'Title', 'Duties']].head(2), headers='keys', tablefmt='pretty', showindex=False,
                       stralign='left'))

        df.to_excel("job_detail.xlsx", index=False)

    else:
        print(f"Failed to fetch page. Status code: {response.status_code}")

except Exception as e:
    print(f"Error: {e}")