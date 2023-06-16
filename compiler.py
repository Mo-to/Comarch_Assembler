import configparser
import os.path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# The ID and range of a sample spreadsheet.
config = configparser.ConfigParser()
config.read('config.ini')
SPREADSHEET_ID = config['DEFAULT']['SpreadsheetId']
CODE_RANGE = 'Code!A4:X35'
CODE_FILE_NAME = 'code.txt'


def read_code_df(spreadsheet_id: str, sheets_range: str):
    """
    Return values in a range of a spreadsheet as pandas df
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                    range=sheets_range).execute()
        values = result.get('values', [])

        return pd.DataFrame(values)
    except HttpError as err:
        print(err)


def get_command_to_code_dict(df: pd.DataFrame):
    """
    Return a dict of command to 5-bit code
    """
    command_to_code = {}
    for row in df.itertuples():
        if row[6] != '':
            code_val_dec = int('000' + str(row[1]) + str(row[2]) + str(row[3]) + str(row[4]) + str(row[5]), 2)
            code_val_hex = f'{code_val_dec:x}'
            param_command = parse_param_command(row[6])  # Returns a dict with keys: command_name, params
            code_name = param_command.get('command_name')
            params = param_command.get('params')

            command_to_code[code_name] = {
                'code_val': code_val_hex,
                'param_num': len(params),
                'params': params,
            }
    return command_to_code


def parse_param_command(command: str):
    """
    Parse a command of type NAME <param1> <param2> ... <paramN>, e.g. JMP <addr> to a dict with keys:
    command_name: str
    params: list of str
    """
    command_name = command.split('<')[0]
    params = command.split('<')[1:]
    # Strip the brackets from the params
    params = [param[:-1] for param in params]
    return {
        'command_name': command_name,
        'params': params,
    }


def get_human_code(path: str):
    """
    Read in the file named path and return the human code as a string array separated by line
    :param path:
    :return:
    """
    with open(path, 'r') as f:
        code = f.read()
    return code.split('\n')

def create_hex_code(human_code: list[str], command_to_code: dict):
    """
    Create a hex code from the human code using command_to_code dict
    :param human_code:
    :param command_to_code:
    :return:
    """
    hex_code = []
    for line in human_code:
        if line == '':
            continue
        command_parsed = parse_param_command(line)
        command = command_parsed.get('command_name')
        params = command_parsed.get('params')
        code_hex = command_to_code[command].get('code_val')

        for param in params:
            hex_code.append(param)
    return hex_code


if __name__ == '__main__':
    values = read_code_df(SPREADSHEET_ID, CODE_RANGE)
    print(values)
    command_to_code = get_command_to_code_dict(values)
    print(command_to_code)
    code = get_human_code(CODE_FILE_NAME)
    print(code)
    hex_code = create_hex_code(code, command_to_code)
