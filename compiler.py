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
CODE_RANGE = 'A4:AF35'
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
    COMMAND_ROW = 8

    command_to_code = {}
    for row in df.itertuples():
        if row[COMMAND_ROW] != '':
            code_val_dec = int('000' + str(row[1]) + str(row[2]) + str(row[3]) + str(row[4]) + str(row[5]), 2)
            code_val_hex = f'{code_val_dec:x}'
            param_command = parse_command_definition(row[COMMAND_ROW])  # Returns a dict with keys: command_name, params
            code_name = param_command.get('command_name')
            params = param_command.get('params')

            command_to_code[code_name] = {
                'code_val': code_val_hex,
                'param_num': len(params),
                'params': params,
            }
    return command_to_code


def parse_command_definition(command: str):
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


def create_hex_code(human_code: list[str], commands_dict: dict):
    """
    Create a hex code from the human code using command_to_code dict
    :param human_code:
    :param commands_dict:
    :return:
    """
    hex_code = []
    for line in human_code:
        if line == '':
            continue
        command_parsed = parse_human_command(line, commands_dict)
        command = command_parsed.get('command_name')
        param = command_parsed.get('param')
        code_hex = commands_dict[command].get('code_val')

        if code_hex is not None:
            hex_code.append(code_hex)
            if param != '':
                hex_code.append(param)

    # Lambda to convert the hex codes from ['f', '0', '4', '5', 'd', '02'] to ['0f', '00', '04', '05', '0d', '02']
    hex_code_formatted = lambda lst: [hex(int(x, 16))[2:].zfill(2) for x in lst]
    return hex_code_formatted(hex_code)


def parse_human_command(human_command: str, commands_dict: dict):
    """
    Parse a command of type NAME <value1> <value2> ... <paramN>, e.g. JMP #01 to a dict.
    Parameters:
    human_command: dict
    """
    for command in commands_dict.keys():
        if human_command.startswith(command):
            command_name = command
            code_val = commands_dict[command].get('code_val')
            param = human_command.replace(command, '')
            return {
                'command_name': command_name,
                'code_val': code_val,
                'param': param,
            }
    return None


def parse_to_file(hex_code: list[str], path: str, seperator: str = '\n') -> None:
    """
    Parse the hex code to a file
    :param hex_code: list of hex codes
    :param path: path to file
    """
    with open(path, 'w') as f:
        f.write('\n'.join(hex_code))


def parse_to_program(hex_code: list[str], path: str) -> None:
    """
    Parse the hex code to a file useable by LogisimEvolution
    """
    TEMPLATE_FILE_NAME = 'ProgramTemplate.txt'

    with open(TEMPLATE_FILE_NAME, 'r') as f:
        template = f.read()

    program = template
    for hex in hex_code:
        program = program.replace('<placeholder>', hex, 1)
    program = program.replace('<placeholder>', '00')

    with open(path, 'w+') as f:
        f.write(program)


if __name__ == '__main__':
    values = read_code_df(SPREADSHEET_ID, CODE_RANGE)
    print(values)
    commands_dict = get_command_to_code_dict(values)
    print(commands_dict)
    code = get_human_code(CODE_FILE_NAME)
    print(code)
    hex_code = create_hex_code(code, commands_dict)
    print(hex_code)
    parse_to_file(hex_code, 'hex_code.txt')
    parse_to_program(hex_code, 'Program')