import socket
import threading
import json
import redis

# Redis 설정 9786포트로 클라이언트와 통신
redis_host = 'redis_server'
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port)

# 초기 상태 설정
initial_deck = ["s1", "s2", "s3", "s4", 's5', 's6', 'd7', 's8', 's9', 's10', 'JK']
r.set('card_deck', json.dumps(initial_deck))
r.set('nicknames', json.dumps({}))
r.set('queue', json.dumps([]))
r.set('latest_update', json.dumps({'action': None, 'card_id': None, 'nickname': None}))


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
    nicknames = get_nicknames()
    queue = get_queue()
    latest_update = get_latest_update()
    top_queue = queue[:3]

    message = {
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


def handle_client_request(request):
    data = json.loads(request)
    action = data.get('action')
    card_id = data.get('card_id')
    nickname = data.get('nickname')
    nicknames = get_nicknames()
    queue = get_queue()

    if action == 'see_all':
        see_through_all = {
            'all_register_list': nicknames,
            'all_queue_list': queue
        }
        return json.dumps(see_through_all)

    if action == 'register':
        if nickname in nicknames:
            return json.dumps({'status': 'error', 'message': '이미 뺏긴 이름'})
        if len(nicknames) >= 21:
            return json.dumps({'status': 'error', 'message': '접속중 너무 많은 사용자'})

        nicknames[nickname] = {'status': 'connected'}
        set_nicknames(nicknames)

        return json.dumps({'status': 'success', 'message': '등록 성공적인'})

    elif action == 'claim_queue':
        if nickname not in nicknames:
            return json.dumps({'status': 'error', 'message': '유효하지 않은 접근'})
        if not get_deck():
            return json.dumps({'status': 'error', 'message': '카드 이미 다 가져간'})

        selected_card=str(get_deck()[0])
        remove_card(selected_card,nickname)
        queue.append(nickname)
        set_queue(queue)
        nicknames[nickname] = {'status': 'in_a_queue'}
        return json.dumps({'status': 'success','queue_card': f'{selected_card}'})

    elif action == 'return':
        if nickname not in nicknames:
            return json.dumps({'status': 'error', 'message': '유효하지 않은 접근'})
        if card_id in get_deck():
            return json.dumps({'status': 'error', 'message': '재접속 필요'})

        return_card(card_id, nickname)
        queue = get_queue()
        queue.remove(nickname)
        set_queue(queue)
        nicknames[nickname] = {'status': 'connected'}
        return json.dumps({'status': 'success', 'message': f'{card_id} 반납 '})

    return json.dumps({'status': 'error', 'message': 'Invalid action'})


def handle_client_connection(client_socket, client_address):
    try:
        # 클라이언트와 연결이 이루어졌을 때의 처리
        print(f"Accepted connection from {client_address}")

        # 클라이언트 요청 수신 및 처리
        while True:
            request = client_socket.recv(1024).decode('utf-8')
            if not request:
                break  # 연결이 끊어졌다면 종료
            response = handle_client_request(request)
            client_socket.send(response.encode('utf-8'))

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # 클라이언트 연결 종료 시 카드 반납 및 상태 초기화
        client_socket.close()
        # 클라이언트가 연결 종료 시 카드 자동 반납
        nicknames = get_nicknames()
        if client_address in nicknames:
            nickname = client_address
            # 카드 반납 처리
            for card_id in list(get_deck()):
                return_card(card_id, nickname)
            # 닉네임 및 큐 상태 초기화
            nicknames.pop(nickname, None)
            set_nicknames(nicknames)
            queue = get_queue()
            if nickname in queue:
                queue.remove(nickname)
                set_queue(queue)
            # 최신화된 상태를 클라이언트들에게 전파
            notify_clients()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(20)
    print("Server listening on port 9999")

    while True:
        client_socket, client_address = server.accept()
        client_handler = threading.Thread(target=handle_client_connection, args=(client_socket, client_address))
        client_handler.start()


if __name__ == '__main__':
    start_server()