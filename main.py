import yaml
import os
import logging
import subprocess
import socket
import sys
import docker
from time import sleep
import re
import smtplib

sep = os.sep
SETTINGS_PATH = os.environ['SETTINGS_PATH'] = os.path.abspath('settings.yml')
with open(SETTINGS_PATH, 'r') as f:
    SETTINGS = yaml.safe_load(f)

GIT_FLAG = SETTINGS['PostgresSettings']['IsGit']
BASE_PATH = SETTINGS['BasePath']
ARTEFACTS_PATH = SETTINGS['ArtefactsPath']
POSTGRES_SOURCE = SETTINGS['PostgresSettings']['PostgresSource']
POSTGRES_REPO = SETTINGS['PostgresSettings']['PostgresSource'].split(os.sep)[-1]
BRANCHES = SETTINGS['PostgresSettings']['Branches']
LOGFILE = SETTINGS['BasePath']+f'{sep}fuzz.log'
GIT_CLEAN = f'git -C {POSTGRES_SOURCE} clean -xdf'
SQUIRREL_TIMEOUT = SETTINGS['SquirrelTimeout']
CHECK_TIMEOUT = SETTINGS['CheckTimeout']
GIT_COMPRESS = f'tar --exclude .git -zcf postgres.tar.gz --directory={POSTGRES_SOURCE} .'
COMPRESS = f'tar -zcf postgres.tar.gz --directory={POSTGRES_SOURCE} .'
EMAILSENDER = SETTINGS['Email']['senderlogin']
EMAILPASS = SETTINGS['Email']['senderpassword']
EMAILRECIEVERS = SETTINGS['Email']['receivers'].split(',')
SMTP_SERVER = SETTINGS['Email']['smtp']
PORT = SETTINGS['Email']['port']
local_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
test_env = os.environ.copy()
client = docker.from_env()


if sys.version_info[0] == 3:
    if sys.version_info[1] > 8:
        logging.basicConfig(filename=LOGFILE, encoding='utf-8',
                            level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    else:
        logging.basicConfig(filename=LOGFILE,
                            level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
else:
    sys.exit('How do you even get there?!')


# def error_processing(err: str):
#     if "did not match any file(s) known to git" in err:
#         logging.error(f'[!] There is no such branch ({BRANCH}) in the repository. Check the yml configfile')
#         sys.exit('[!] There is no such branch in the repository')
#     if 'fatal: not a git repository' in err:
#         logging.error(f'[!] {POSTGRES_SOURCE} is not a git repo. Check the yml configfile')
#         sys.exit('Not a git repo')
    
def append_to_containers_list(container_name: str):
    with open(f'{BASE_PATH}{sep}containers', 'a') as f:
        f.write(f'{container_name}\n')


def send_mail(email_receivers: list, email_message: str):
    sender = EMAILSENDER
    sender_password = EMAILPASS
    mail_con = smtplib.SMTP_SSL(SMTP_SERVER, int(PORT))
    mail_con.login(sender, sender_password)
    for to_item in email_receivers:
        msg = 'From: %s\r\nTo: %s\r\nContent-Type: text/plain; charset="utf-8"\r\nSubject: %s\r\n\r\n' % (
        sender, to_item, 'Postgres GenFuzz reuslts')
        msg += email_message
        mail_con.sendmail(sender, to_item, msg.encode('utf8'))
    mail_con.quit()


def run_subproc(cmd: str, msg: str, env=test_env):
    logging.info(msg)
    res = subprocess.run(cmd.split(), env=env, capture_output=True, text=True)
    if res.stderr:
        logging.error(f'[!] {res.stderr}')


def check_git_repo(branch: str):
    GIT_CHECK1 = f'git -C {POSTGRES_SOURCE} branch -a'
    GIT_CHECK2 = f'grep -E {branch}$'
    branches = subprocess.run(GIT_CHECK1.split(' '), capture_output=True, check=True)
    res = subprocess.run(GIT_CHECK2.split(), input=branches.stdout, capture_output=True)
    if branches.stderr:
        sys.exit('[!] This is not a git repo! Check the yml config!')
    if not res.stdout:
        sys.exit('[!] There is no such branch in the repository')


def prepare_source(branch: str):
    run_subproc("rm -f postgres.tar.gz", f'Delete old tarball')
    GIT_CHECKOUT = f'git -C {POSTGRES_SOURCE} checkout {branch}'
    if GIT_FLAG:
        check_git_repo(branch)
        run_subproc(GIT_CHECKOUT, f'[+] Checkout to {branch}')
        run_subproc(GIT_CLEAN, f'[+] Clean up old build artefacts')
        run_subproc(GIT_COMPRESS, f'[+] Compressing the source repo')
    else:
        run_subproc(COMPRESS, f'[+] Compressing the source repo')
    

def start_sqlancer(fullver: str, context=BASE_PATH) -> bool:
    if int(fullver.split('.')[0]) < 13:
        logging.info('[!] This tool works properly for PostgreSQL version >= 13. Skipping this version...')
        return False
    try:
        client.images.get(f"sqlancer:postgres-{fullver}")
        logging.debug('[*] Docker image was found successfuly! Initializing...')
    except docker.errors.ImageNotFound:
        logging.debug('[*] Wait for image build ...')
        try:
            client.images.build(path=context, dockerfile=f'{context}{sep}sqlancer{sep}dockerfile',
                            tag=f'sqlancer:postgres-{fullver}', rm=True)
        except docker.errors.BuildError as e:
            if 'mvn package -DskipTests' in e:
                client.images.build(path=context, dockerfile=f'{context}{sep}sqlancer{sep}dockerfile',
                            tag=f'sqlancer:postgres-{fullver}', rm=True)
            else:
                logging.error(f'[!] Check if this version of postgres is compatible with sqlancer. Minimal version is 13. In other cases you should check folders and scripts structure in {BASE_PATH}.\n Here the exception occured:\n {e}')
                return False
        logging.debug('[*] Docker image was built successfuly! Initializing...')
    client.containers.run(f'sqlancer:postgres-{fullver}', name=f'sqlancer-{fullver}',
                          stdin_open=True, 
                          detach=True, 
                          privileged=True,
                          environment={"VERSION": fullver},
                          volumes={f'{ARTEFACTS_PATH}': {'bind': '/opt/arts', 'mode': 'rw'}})
    append_to_containers_list(f'sqlancer-{fullver}')
    logging.info(f'[+] A container with sqlancer and postgres-{fullver} has started successfully. Name of the container is sqlancer-{fullver}')
    return True


def start_squirrel(fullver: str, context=BASE_PATH) -> bool:
    try:
        client.images.get(f"squirrel:postgres-{fullver}")
        logging.debug('[*] Docker image was found successfuly! Initializing...')
    except docker.errors.ImageNotFound:
        logging.debug('[*] Wait for image build ...')
        try:
            client.images.build(path=context, dockerfile=f'{context}{sep}squirrel{sep}dockerfile',
                            tag=f'squirrel:postgres-{fullver}', rm=True)
        except docker.errors.BuildError as e:
            logging.error(f'[!] You should check folders and scripts structure in {BASE_PATH}.\n Here the exception occured:\n {e}')
            # sys.exit(f'[!] Error with squirrel build. See the {LOGFILE} for detailed explanation')
            return False
        logging.debug('[*] Docker image was built successfuly! Initializing...')
    client.containers.run(f'squirrel:postgres-{fullver}', 
                          name=f'squirrel-{fullver}', 
                          stdin_open=True, 
                          detach=True,
                          environment={"TIMEOUT": SQUIRREL_TIMEOUT,
                                       "VERSION": fullver},
                          volumes={f'{ARTEFACTS_PATH}': {'bind': '/opt/arts', 'mode': 'rw'}})
    append_to_containers_list(f'squirrel-{fullver}')
    logging.info(f'[+] A container with squirrel and postgres-{fullver} has started successfully. Name of the container is squirrel-{fullver}')
    return True


def check_squirrel(containers: list) -> bool:
    for container in containers:
        if container.startswith('squirrel'):
            return True
    return False


def main():  
    run_subproc(f'git -C {POSTGRES_SOURCE} pull', f'[+] Pulling the source repo')
    for branch,name in BRANCHES.items():
        prepare_source(branch)
        majorver = name.split('-')[0]
        fullver_location = f'{POSTGRES_SOURCE}/doc/src/sgml/ru/version.sgml'
        try:
            with open(fullver_location, 'rt') as f:
                fullver = re.search(r'[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}', f.read()).group(0)
        except FileNotFoundError:
            fullver=majorver
        sqlancer_status = start_sqlancer(fullver)
        squirrel_status = start_squirrel(fullver)
        if sqlancer_status:
            logging.info('[+] Sqlancer fuzzing started succesfully')
        if squirrel_status:
            logging.info('[+] Squirrel fuzzing started succesfully')
    run_subproc("rm -f postgres.tar.gz", f'[+] Delete old tarball')
    with open('containers', 'r') as f:
        containers = f.read().splitlines()
    squirrel_flag = False
    while True:
        if containers:
            artefacts = [art[:-7] for art in os.listdir(ARTEFACTS_PATH)]
            artefacts = [art[:art.find('{')]+art[art.rfind('}')+2:] for art in artefacts]
            logging.info('[+] list of available containers: ' + str(containers))
            logging.info('[+] list of available artefacts: ' + str(artefacts))
            for art in artefacts:
                if art in containers:
                    client.containers.get(art).stop()
                    client.containers.get(art).remove()
                    logging.info(f'[+] Container {art} has been stopped and removed')
                    if 'sqlancer' in art:
                        fullver = art.split('-')[2][:-7]
                        send_mail(EMAILRECIEVERS, f'Sqlancer session for postgres-{fullver} has been finished.\nArtefacts can be obtained on the {local_ip} machine in the folder {ARTEFACTS_PATH}')
                    containers.remove(art)
            if not squirrel_flag and containers and not check_squirrel(containers):
                send_mail(EMAILRECIEVERS, f'Squirrel fuzzing is done!\nArtefacts can be obtained on the {local_ip} machine in the folder {ARTEFACTS_PATH}. Sqlancer containers are still running.')
                squirrel_flag = True
            sleep(CHECK_TIMEOUT)
        else:
            artefacts = [art+'\n' for art in os.listdir(ARTEFACTS_PATH)]
            artefacts_str = ''.join(artefacts)
            send_mail(EMAILRECIEVERS, f"The artefacts path specified in the settings is: {local_ip}:{ARTEFACTS_PATH}\nObtained artefacts:\n {artefacts_str}")
            os.remove('containers')
            break


main()