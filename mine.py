import os
import random
import time
import requests
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import RequestException
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def doreamon_banner():
    banner_text = r"""
██████╗  ██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗ ██████╗ ███╗   ██╗
██╔══██╗██╔═══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔═══██╗████╗  ██║
██║  ██║██║   ██║██████╔╝█████╗  ███████║██╔████╔██║██║   ██║██╔██╗ ██║
██║  ██║██║   ██║██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██║   ██║██║╚██╗██║
██████╔╝╚██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║
╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝                                                                      
              MADE BY :- Đôrêmon
    """
    console.print(Panel(banner_text, style="bold green"))

class NodeGoPinger:
    def __init__(self, token, proxy_urls=[]):
        self.api_base_url = 'https://nodego.ai/api'
        self.bearer_token = token
        self.proxy_urls = proxy_urls
        self.session_cache = {}
        self.last_ping_timestamp = 0

    def create_proxy_session(self, proxy_url):
        if proxy_url in self.session_cache:
            return self.session_cache[proxy_url]

        session = requests.Session()
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        session.proxies.update(proxies)

        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

        self.session_cache[proxy_url] = session
        return session

    def generate_node_id(self):
        return f'node_{random.randint(0, 999999)}'

    def get_user_info(self, proxy_url):
        try:
            response = self.make_request('GET', '/user/me', proxy_url)
            metadata = response.json().get('metadata', {})
            return {
                'username': metadata.get('username'),
                'email': metadata.get('email'),
                'totalPoint': metadata.get('rewardPoint'),
                'nodes': [
                    {
                        'id': node['id'],
                        'totalPoint': node['totalPoint'],
                        'todayPoint': node['todayPoint'],
                        'isActive': node['isActive']
                    } for node in metadata.get('nodes', [])
                ]
            }
        except RequestException as e:
            console.print(f"[bold red]Failed to fetch user info with proxy {proxy_url}: {str(e)}[/bold red]")
            raise

    def make_request(self, method, endpoint, proxy_url, data=None):
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            'Authorization': f"Bearer {self.bearer_token}",
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }

        session = self.create_proxy_session(proxy_url)
        retries = 3
        attempt = 0

        while attempt < retries:
            try:
                if method == 'GET':
                    response = session.get(url, headers=headers, timeout=30)
                elif method == 'POST':
                    response = session.post(url, headers=headers, json=data, timeout=30)

                response.raise_for_status()
                console.print(f"[bold green]Successfully connected with proxy: {proxy_url}[/bold green]")
                return response
            except RequestException as e:
                attempt += 1
                console.print(f"[yellow]Attempt {attempt}/{retries} failed with proxy {proxy_url}: {str(e)}[/yellow]")
                if attempt == retries:
                    console.print(f"[bold red]Request failed after {retries} attempts with proxy {proxy_url}: {str(e)}[/bold red]")
                    raise
                time.sleep(5)

    def ping(self, proxy_url):
        current_time = int(time.time() * 1000)
        if current_time - self.last_ping_timestamp < 3000:
            time.sleep(3 - (current_time - self.last_ping_timestamp) / 1000)

        node_id = self.generate_node_id()
        try:
            response = self.make_request('POST', '/user/nodes/ping', proxy_url, {
                'type': 'extension',
                'nodeId': node_id
            })
            self.last_ping_timestamp = current_time
            return {
                'statusCode': response.json().get('statusCode'),
                'message': response.json().get('message'),
                'metadataId': response.json().get('metadata', {}).get('id'),
                'nodeId': node_id
            }
        except RequestException as e:
            console.print(f"[bold red]Ping failed with proxy {proxy_url}: {str(e)}[/bold red]")
            raise

    def start_keep_alive_ping(self, proxy_url):
        while True:
            try:
                console.print(f"[blue]Sending keep-alive ping to proxy: {proxy_url}[/blue]")
                ping_response = self.ping(proxy_url)
                console.print(f"[green]Keep-alive ping successful! Node ID: {ping_response['nodeId']}[/green]")
            except RequestException as e:
                console.print(f"[red]Keep-alive ping failed with proxy {proxy_url}: {str(e)}[/red]")
                time.sleep(5)
            time.sleep(5)

class MultiAccountPinger:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.is_running = True

    def load_accounts(self):
        accounts = []
        try:
            with open('token.txt', 'r') as f:
                account_data = f.read().splitlines()

            proxy_data = []
            if os.path.exists('proxies.txt'):
                with open('proxies.txt', 'r') as f:
                    proxy_data = f.read().splitlines()

            for token in account_data:
                accounts.append({
                    'token': token.strip(),
                    'proxyUrls': proxy_data
                })
        except Exception as e:
            console.print(f"[bold red]Error reading accounts: {str(e)}[/bold red]")
            exit(1)
        return accounts

    def process_single_account(self, account):
        pinger = NodeGoPinger(account['token'], account['proxyUrls'])

        for proxy_url in account['proxyUrls']:
            console.print(Panel(f"Connecting to proxy: [cyan]{proxy_url}[/cyan]", style="bold magenta"))
            try:
                user_info = pinger.get_user_info(proxy_url)
                if not user_info:
                    continue

                ping_response = pinger.ping(proxy_url)

                table = Table(title="User Information", title_style="bold green")
                table.add_column("Field", style="bold cyan")
                table.add_column("Value", style="bold magenta")

                table.add_row("Username", user_info['username'])
                table.add_row("Email", user_info['email'])
                table.add_row("Total Points", str(user_info['totalPoint']))

                console.print(table)

                node_table = Table(title="Node Details", title_style="bold yellow")
                node_table.add_column("Node ID", style="bold blue")
                node_table.add_column("Total Points", style="bold green")
                node_table.add_column("Today's Points", style="bold yellow")
                node_table.add_column("Status", style="bold red")

                for node in user_info['nodes']:
                    status = "Active" if node['isActive'] else "Inactive"
                    node_table.add_row(
                        node['id'],
                        str(node['totalPoint']),
                        str(node['todayPoint']),
                        status
                    )

                console.print(node_table)

                console.print(Panel(
                    f"Status Code: [green]{ping_response['statusCode']}[/green]\n"
                    f"Message: [green]{ping_response['message']}[/green]\n"
                    f"Generated Node ID: [cyan]{ping_response['nodeId']}[/cyan]\n"
                    f"Metadata ID: [magenta]{ping_response['metadataId']}[/magenta]",
                    title=f"Ping Response (Proxy: [cyan]{proxy_url}[/cyan])",
                    style="bold white"
                ))

                time.sleep(5)
            except RequestException as e:
                console.print(f"[bold red]Error processing account with proxy {proxy_url}: {str(e)}[/bold red]")

    def run_pinger(self):
        doreamon_banner()  # Display the custom Doreamon banner at startup.
        while self.is_running:
            console.print(f"\n[yellow]⏰ Ping Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}[/yellow]")
            for account in self.accounts:
                if not self.is_running:
                    break
                self.process_single_account(account)
            if self.is_running:
                time.sleep(15)

if __name__ == '__main__':
    multi_pinger = MultiAccountPinger()
    multi_pinger.run_pinger()
