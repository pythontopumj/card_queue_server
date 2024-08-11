import socket
import threading
import json
import redis
import time
import logging

# 로깅 설정

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 로그 레벨을 DEBUG로 설정

# 파일 핸들러 설정
file_handler = logging.FileHandler('card_sv.log')
file_handler.setLevel(logging.DEBUG)  # 파일 핸들러에 대한 로그 레벨 설정

# 포맷터 설정
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 로거에 핸들러 추가
logger.addHandler(file_handler)
# Redis 설정
redis_host = 'redis_server'
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port)

initial_deck = ["s1", "s2", "s3", "s4", 's5', 's6', 'd7', 's8', 's9', 's10', 'JK']
r.set('card_deck', json.dumps(initial_deck))#카드를 뽑고 반납하는 카드덱
r.set('nicknames', json.dumps({}))#nickname:str(adress)
r.set('queue', json.dumps([]))#[nickname]
r.set('jangbu', json.dumps({}))#{nickname:card} 보통은 큐를 사용하고 특수한 경우를 위해 큐 추적을 위해 신설
r.set('latest_update', json.dumps({'action': None, 'card_id': None, 'nickname': None}))#가장 최신 정보


# 클라이언트 연결을 저장하는 리스트
clients = []
class subs_storage:#클라이언트 구독용 구독소켓 정보, 구독자 소켓 인스턴스 전체 리스트, 각 구독자별 읽지 않은 메세지 저장, 쓰레드lock을 통해 모든 쓰레드에서 동기화
    socket_instances=[]#소켓 인스턴스들을 저장
    cs_lock = threading.Lock()

    def __init__(self,socket):
        self.islock = threading.Lock()
        self.reset_instance_storage()
        self.add_socket(self)
        self.saving_socket(socket)

    def saving_socket(self,socket):
        with self.islock:
            self.socket=socket

    def who_i_am(self):
        with self.islock:
            return self.socket

    @classmethod
    def remove_socket(cls, item):
        with cls.cs_lock:  # 클래스 변수 접근 시 락을 사용
            cls.socket_instances.remove(item)

    @classmethod
    def add_socket(cls, item):
        with cls.cs_lock:  # 클래스 변수 접근 시 락을 사용
            cls.socket_instances.append(item)

    @classmethod
    def get_socket_list(cls):
        with cls.cs_lock:
            return cls.socket_instances.copy()  # 읽기와 동시에 데이터 경합을 방지하기 위해 복사본 반환

    def reset_instance_storage(self):
        with self.islock:
            self.subs_store=[]

    def remove_instance_storage(self, item):
        with self.islock:
            self.subs_store.remove(item)
    def add_to_instance_storage(self, item):
        with self.islock:
            self.subs_store.append(item)
    def get_instance_storage(self):
        with self.islock:
            return self.subs_store.copy()

    @classmethod
    def remove_instance_by_socket(cls, client_socket):
        """특정 소켓을 통해 생성된 인스턴스를 찾아 제거합니다."""
        with cls.cs_lock:
            for instance in cls.socket_instances:
                if instance.socket == client_socket:
                    # 소켓 종료
                    try:
                        instance.socket.close()
                    except Exception as e:
                        logger.info(f"Error closing socket: {e}")

                    # 인스턴스 리스트에서 제거
                    cls.socket_instances.remove(instance)

                    # 인스턴스 자체 삭제
                    del instance
                    break  # 인스턴스를 찾으면 루프를 종료


def subs_store(message):
    """모든 유저의 클래스 subs_storage를 통해 생성된 클라이언트 인스턴스 저장소에 메세지를 추가합니다."""
    socket_list=subs_storage.get_socket_list
    for client_socket in socket_list:
        client_socket.add_to_instance_storage(message)

def handle_sub_message(message):
    """Redis 메시지를 처리하고 클라이언트에게 전달합니다."""
    if isinstance(message, int):
        # 메시지가 정수인 경우는 처리하지 않거나 로그를 남길 수 있음
        logger.info(f"Received integer message: {message}")
        return
    message_str = message.decode('utf-8')
    logger.info(f"storing: {message_str}")
    subs_store(message_str)

def get_jangbu():
    return json.loads(r.get('jangbu'))
def set_jangbu(jangbu):
    r.set('jangbu', json.dumps(jangbu))

def get_deck():
    return json.loads(r.get('card_deck'))

def set_deck(deck):
    r.set('card_deck', json.dumps(deck))

def get_nicknames():
    return json.loads(r.get('nicknames'))

def set_nicknames(nicknames):
    r.set('nicknames', json.dumps(nicknames))

def get_queue():
    return json.loads(r.get('queue'))

def set_queue(queue):
    r.set('queue', json.dumps(queue))

def get_latest_update():
    return json.loads(r.get('latest_update'))

def set_latest_update(action, card_id, nickname):
    r.set('latest_update', json.dumps({'action': action, 'card_id': card_id, 'nickname': nickname}))

def notify_clients():
    deck = get_deck()
    queue = get_queue()
    latest_update = get_latest_update()
    top_queue = queue[:3]

    message = {
        'status':"publish",
        'card_deck': len(deck),
        'top_queue': top_queue,
        'latest_update': latest_update
    }

    r.publish('status_updates', json.dumps(message))

def remove_card(card_id, nickname):
    deck = get_deck()
    if card_id in deck:
        deck.remove(card_id)
        set_deck(deck)
        set_latest_update('remove', card_id, nickname)
        notify_clients()

def return_card(card_id, nickname):
    deck = get_deck()
    if card_id not in deck:
        deck.append(card_id)
        set_deck(deck)
        set_latest_update('return', card_id, nickname)
        notify_clients()

def handle_client_request(request,client_socket,client_address):
    data = json.loads(request)
    action = data.get('action')
    card_id = data.get('card_id')
    nickname = data.get('nickname')
    registered_list = get_nicknames()
    queue = get_queue()
    jangbu=get_jangbu()


    if action == 'see_all':
        see_through_all = {
            'all_register_list': registered_list,
            'all_queue_list': queue
        }
        return json.dumps(see_through_all)

    if action == 'register':
        if nickname in registered_list:
            return json.dumps({'status': 'error', 'message': '이미 뺏긴 이름'})
        if len(registered_list) >= 21:
            return json.dumps({'status': 'error', 'message': '접속중 너무 많은 사용자'})

        registered_list[nickname] = str(client_address)
        set_nicknames(registered_list)
        making_class=subs_storage(client_socket)#register에 성공하면 구독 클래스에 해당 소켓 인스턴스 생성, 등록에 성공한 유저에게만 구독정보를 발송
        return json.dumps({'status': 'success', 'message': '등록 성공적인'})

    elif action == 'claim_queue':
        if nickname not in registered_list:
            return json.dumps({'status': 'error', 'message': '유효하지 않은 접근'})
        if not get_deck():
            return json.dumps({'status': 'error', 'message': '카드 이미 다 가져간'})

        selected_card = str(get_deck()[0])
        remove_card(selected_card, nickname)
        queue.append(nickname)
        jangbu[nickname]=selected_card
        set_jangbu(jangbu)
        set_queue(queue)

        return json.dumps({'status': 'success', 'queue_card': f'{selected_card}'})

    elif action == 'return':
        if nickname not in registered_list:
            return json.dumps({'status': 'error', 'message': '유효하지 않은 접근'})
        if card_id in get_deck():
            return json.dumps({'status': 'error', 'message': '재접속 필요'})

        return_card(card_id, nickname)
        queue = get_queue()
        queue.remove(nickname)
        jangbu.pop(nickname)
        set_jangbu(jangbu)
        set_queue(queue)
        return json.dumps({'status': 'success', 'message': f'{card_id} 반납 '})

    return json.dumps({'status': 'error', 'message': 'Invalid action'})

def handle_client_connection(client_socket, client_address):
    """클라이언트와의 연결을 처리합니다."""
    try:
        # 클라이언트와 연결이 이루어졌을 때의 처리
        logger.info(f"Accepted connection from {client_address}")

        # 클라이언트 연결 리스트에 추가
        clients.append(client_socket)

        # 클라이언트 요청 수신 및 처리
        while True:
            request = client_socket.recv(1024).decode('utf-8')
            if not request:
                logger.info("Client disconnected or sent an empty request.")
                break  # 연결이 끊어졌다면 종료
            response = handle_client_request(request,client_socket, client_address)
            client_socket.send(response.encode('utf-8'))


    except Exception as e:
        logger.info(f"Error: {e}")

    finally:
        # 클라이언트 연결 종료 시 카드 반납 및 상태 초기화
        def find_gone_user(dict_, target_value):
            return [key for key, value in dict_.items() if value == target_value]
        try:
            subs_storage.remove_instance_by_socket(client_socket)#소켓 연결을 종료 전 메모리 관리를 위해 substore 클래스의 인스턴스 삭제
        except:
            logger.info("socket doesnt exist in instance")
        client_socket.close()
        clients.remove(client_socket)
        # 클라이언트가 연결 종료 시 카드 자동 반납
        registered_list = get_nicknames()
        jangbu=get_jangbu()
        queue = get_queue()
        if str(client_address) in registered_list.values():
            discon_user_list=find_gone_user(registered_list,str(client_address))
            for discon_user in discon_user_list:
                nickname = discon_user
                registered_list.pop(nickname, None)
                set_nicknames(registered_list)
                if nickname in queue:
                    return_card(jangbu[nickname],nickname)
                    queue.remove(nickname)
                    jangbu.pop(nickname)
                    set_jangbu(jangbu)
                    set_queue(queue)
            # 최신화된 상태를 클라이언트들에게 전파


def start_server():
    """서버를 시작합니다."""
    logger.info("before start")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(20)
    logger.info("Server listening on port 9999")

    # Redis 구독을 위한 스레드 시작
    def redis_subscriber():
        pubsub = r.pubsub()
        pubsub.subscribe('status_updates')

        for message in pubsub.listen():
            if message['type'] == 'message':
                # 메시지 형식을 확인합니다
                if isinstance(message['data'], bytes):
                    message_str = message['data'].decode('utf-8')
                    handle_sub_message(message_str)

    redis_thread = threading.Thread(target=redis_subscriber)
    redis_thread.daemon = True
    redis_thread.start()

    def around_the_user_for_sub():# 구독정보를 처리하기 위한 쓰레드
        while True:
            time.sleep(1)
            subs_class=subs_storage
            list_for_user=subs_class.get_socket_list()
            for user in list_for_user:
                socket_for_broad=user.who_i_am()
                sub_list=user.get_instance_storage()
                for messages in sub_list:
                    try:
                        socket_for_broad.send(messages.encode('utf-8'))
                        user.remove_instance_storage(messages)
                    except Exception as e:
                        logger.info(f"Error sending message to client: {e}")

    sending_subs = threading.Thread(target=around_the_user_for_sub)
    sending_subs.start()


    while True:
        client_socket, client_address = server.accept()
        client_handler = threading.Thread(target=handle_client_connection, args=(client_socket, client_address))
        client_handler.start()




if __name__ == '__main__':
    start_server()
