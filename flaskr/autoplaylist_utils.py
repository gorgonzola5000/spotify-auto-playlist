import requests
from flask import session, url_for
import time
import json
from .TokenExpiredError import TokenExpiredError

def get_playlists():
    headers = {
    'Authorization': f'Bearer {session["authorization_token"]}'
    }
    url = 'https://api.spotify.com/v1/me/playlists'
    playlists_dict = {}

    while True:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise TokenExpiredError()
            else:
                raise
        response_json = response.json()  # get the page of playlists of the user
        for item in response_json['items']:
            if item['images']:
                temp_dict = {
                    "name": item['name'],
                    "ap_id": None,
                    "public": item['public'],
                    "image": item['images'][0]['url'],
                    "tracks_total": item['tracks']['total']
                }
            else:
                temp_dict = {
                    "name": item['name'],
                    "ap_id": None,
                    "public": item['public'],
                    "image": url_for('static', filename='default_playlist_image.png'),
                    "tracks_total": item['tracks']['total']
                }
            playlists_dict[item['id']] = temp_dict

        url = response_json['next']
        if url is None:  # if there is no next page, break the loop
            break
        time.sleep(2)  # sleep for 2 seconds before the next request

    session['user_playlists'] = playlists_dict

    for key in playlists_dict:
        item = playlists_dict[key]
        if item['name'].endswith(' AP'):
            name_without_ap = item['name'].replace(' AP', '')
            for key2 in playlists_dict:
                item2 = playlists_dict[key2]
                if item2['name'] == name_without_ap:
                    session['user_playlists'][key2]["ap_id"] = key

def get_tracks(playlist_id):
    headers = {
        'Authorization': f'Bearer {session["authorization_token"]}'
    }
    data = {
        'offset': 0,
        'limit': 50
    }
    tracks_dict = {}
    while True: # do
        try:
            tracks_temp = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers = headers, params = data)
            tracks_temp.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise TokenExpiredError()
            else:
                raise
        tracks_temp_json = tracks_temp.json()
        for item in tracks_temp_json['items']:
            temp_dict = {
                "name": item['track']['name'],
                "artist": item['track']['artists'][0]['name'],
                "album": item['track']['album']['name'],
                "image": item['track']['album']['images'][0]['url'],
                "uri": item['track']['uri']
                # "genres": item['track']['artists'][0]['genres']
            }
            tracks_dict[item['track']['id']] = temp_dict
        data['offset'] += 50
        time.sleep(2)
        if tracks_temp_json['next'] == None: # while tracks_temp['next'] != None, so while there are more pages of tracks
            break
    return tracks_dict

def create_playlist(playlist_id):
    headers = {
    'Authorization': f'Bearer {session["authorization_token"]}',
    'Content-Type': 'application/json'
    }
    data = {
        'name': f"{session['user_playlists'][playlist_id]['name']} AP",
        'public': False
    }
    try:
        response = requests.post(f'https://api.spotify.com/v1/users/{session["user_id"]}/playlists', headers=headers, data=json.dumps(data))
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 401:
            raise TokenExpiredError()
        else:
            raise
    response_json = response.json()

    session['user_playlists'][playlist_id]['ap_id'] = response_json['id']
    session.modified = True
    clone_playlist(playlist_id)

def get_user_id():
    if 'authorization_token' in session:
        headers = {
            'Authorization': f'Bearer {session["authorization_token"]}'
        }
        try:
            response = requests.get('https://api.spotify.com/v1/me', headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise TokenExpiredError()
            else:
                raise
        response_json = response.json()
        session['user_id'] = response_json['id']
        return {'profile': response_json}
    else:
        return {}

def filter_tracks(playlist_id, criteria):
    tracks = get_tracks(playlist_id)
    tracks_to_be_filtered_out = []
    for track_id in tracks:
        track = tracks[track_id]
        if criteria in track['artist']:
            tracks_to_be_filtered_out.append(track['uri'])
    return tracks_to_be_filtered_out

def remove_tracks_from_ap_playlist(playlist_id, tracks_to_be_filtered_out):
    ap_playlist_id = session['user_playlists'][playlist_id]['ap_id']
    for i in range(0, len(tracks_to_be_filtered_out), 100):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {session["authorization_token"]}'
        }
        data = {
            'tracks': [{'uri': uri} for uri in tracks_to_be_filtered_out[i:i+100]]
        }
        try:
            requests.delete(f'https://api.spotify.com/v1/playlists/{ap_playlist_id}/tracks', headers=headers, data=json.dumps(data))
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise TokenExpiredError()
            else:
                raise

def clone_playlist(playlist_id):
    ap_playlist_id = session['user_playlists'][playlist_id]['ap_id']
    tracks = get_tracks(playlist_id)
    track_uris = [track['uri'] for track in tracks.values()]

    for i in range(0, len(track_uris), 100):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {session["authorization_token"]}'
        }
        data = {
            'uris': track_uris[i:i+100]
        }
        try:
            response = requests.post(f'https://api.spotify.com/v1/playlists/{ap_playlist_id}/tracks', headers=headers, data=json.dumps(data))
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 401:
                raise TokenExpiredError()
            else:
                raise
            
def reset_playlist(playlist_id):
    ap_playlist_id = session['user_playlists'][playlist_id]['ap_id']
    tracks = get_tracks(ap_playlist_id)
    track_uris = [track['uri'] for track in tracks.values()]
    remove_tracks_from_ap_playlist(playlist_id, track_uris)
    clone_playlist(playlist_id)