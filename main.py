#  Before using this flask application for Cisco Spark webhook,
#  you need to conigure the webhook using python script: 
#      $python3 /home/dyoshiha/CiscoSpark/CiscoSparkCreateWebhook.py
#  or Cisco's website at
#      https://developer.ciscospark.com/endpoint-webhooks-post.html
#

debug_mode = False
#debug_mode = True

# Imports
import requests
import json
import os
import shutil
import io
#import datetime
import math
from PIL import Image
import random
import numpy as np
import pandas as pd
from pandas.io import gbq

import re

# Imports flask
from flask import Flask
from flask import request
from flask import render_template

# Imports the Google Cloud client library
from google.cloud import vision
from google.cloud.vision import types

# Imports swiftstack
import boto3

# Imports Cassandra
from cassandra.cluster import Cluster
from cassandra.query import dict_factory

# Imports Azure
import Azure

### GCP Vision API
client = vision.ImageAnnotatorClient()

###CiscoSpark
bot_access_code = 'MDkzMDI5ZWMtMmNhMS00OGQ3LThkZjUtODQzMmExN2YzZTExNTJhNzg4N2EtNjQ4'
#access_code = 'NTYyZjNhNTUtMDllYi00N2IzLWEzOWYtMGI1ZGVkYTYyNjc4MzYwMjlkMjYtOGE2'
access_code = 'OGJjZWJhMWItZTEyNS00ODJhLThkMTQtNzgxY2FkODA1MGQxYTlkNWNlMWMtZDE1'
base_url = 'https://api.ciscospark.com/v1/messages/'
base_room_url = 'https://api.ciscospark.com/v1/rooms/'
headers = {
    'Authorization' : 'Bearer ' + access_code,
    'Content-Type' : 'application/json'
}

bot_headers = {
    'Authorization' : 'Bearer ' + bot_access_code,
    'Content-Type' : 'application/json'
}

###Swiftstack
session = boto3.Session()
s3 = session.resource('s3', endpoint_url = 'http://172.16.0.11')
#bucket = s3.create_bucket(Bucket = 'DL_Demo_bucket')

###Cassandra
keyspace = "test"
columnFamily = "clouddays"

### SwiftStack
swift_bucket_name = "SmarterCoffee"

### Google Big Query
project_id = 'winged-citron-215214'
data_set = 'GoogleNext_CoffeeData.result'

def prettyJSON(target):
    return json.dumps(target, indent = 4)


def CoffeeMessage(strength):
    coffee_strength = ""

    if strength == "strong":
        coffee_strength = "濃いめで"
    elif strength == "weak":
        coffee_strength = "薄めで"

    message = "コーヒーを{0}お淹れいたします。".format(coffee_strength)

    return message


def RemoveTempFile(file_name):
    original_file, ext = os.path.splitext(file_name)
    os.remove(file_name)
    os.remove(original_file)

def BigQueryInsertData(score, roomId, imgInfo, strength):
    roomName = CiscoSparkGetRoomName(roomId)
    roomName_short = roomName.split()[-2]
    df = pd.DataFrame({
        'createtime' : [pd.Timestamp.now()],
        'score' : [score],
        'roomId' : [roomId],
        'roomName' : [roomName_short],
        'fullRoomName' : [roomName],
        'imgMeta' : [json.dumps(imgInfo)],
        'strength' : [strength]
    })

    df.to_gbq(data_set, project_id, if_exists='append')

def strength_calc(score):
    strength = ""
    if score <= 55:
        strength = 'weak'
    elif score <= 85:
        strength = 'medium'
    else:
        strength = 'strong'
    app.logger.debug("Strength :%s" % strength)
    return strength

def IFTTT_make_coffee(roomId, strength):
    room = "white"
    roomName = CiscoSparkGetRoomName(roomId)
    if "black" in roomName.lower():
        room = "black"

    payload = {
      'value1' : strength
    }

    ifttt_headers = {
      'Content-Type' : 'application/json'
    }

    url = 'https://maker.ifttt.com/trigger/SmarterFaceRecognition_{0}_{1}/with/key/x5t68o1vtfe8ZdtGWjVdy'.format(room, strength)

    app.logger.debug("IFTTT URL: '%s'" % url)
    r = requests.post(url, data = json.dumps(payload), headers = ifttt_headers)
    return True

def CiscoSparkGetRoomName(roomId):
    roomName = None
    try:
        url = base_room_url + roomId
        app.logger.debug(url)
        r = requests.get(url, headers = bot_headers)
        app.logger.debug(prettyJSON(r.json()))
        roomName = r.json()["title"]
    except:
        app.logger.debug("Room name for ID %s was not found." % roomId)
    return roomName

def CiscoSparkPostMessage(post_message, roomId):
    payload = {
      'roomId' : roomId,
      'text' : post_message
    }
    url = base_url
    r = requests.post(url, data = json.dumps(payload), headers = bot_headers)
    return True

def CiscoSparkGetMessage(message_id):
    url = base_url + message_id
    r = requests.get(url, headers = headers)
    return r.json()

def CiscoSparkGetContent(file_url):
    # This function was created based on the code at https://torina.top/detail/161/
    file_name = os.path.basename(file_url)
    url = file_url
    r = requests.get(url, headers = headers, stream = True)
    if r.status_code == 200:
        with open(file_name, 'wb') as file:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, file)
    return file_name

def GoogleCloudPlatformVisionAPI(file_name):
    # Instantiates a client
    client = vision.ImageAnnotatorClient()
    
    # The name of the image file to annotate
    file_path = os.path.join(
        os.path.dirname(__file__),
        file_name)
    
    # Loads the image into memory
    with io.open(file_path, 'rb') as image_file:
        content = image_file.read()
    
    image = types.Image(content=content)
    
    # Performs label detection on the image file
    response = client.face_detection(image=image)
    faces = response.face_annotations
    ### Use the following insted, in case of "Label Detection" ###
    #response = client.label_detection(image=image)
    #labels = response.label_annotations
     
    return faces

def SwiftstackUploadPhoto(file_name, swift_bucket_name):
    my_bucket = s3.Bucket(swift_bucket_name)
    #timesnapshot = datetime.datetime.now()
    
    # Upload .png file (Photo)
    #swiftkey1 = '{0:%Y%m%d_%H%M%S}.png'.format(timesnapshot)
    data = open(file_name, 'rb')
    #my_bucket.put_object( Key = swiftkey1, Body = data )
    my_bucket.put_object( Key = file_name, Body = data )
    
    return

def CassandraInsertData(score, roomId, imgInfo):
    cluster = Cluster(['172.16.0.13','172.16.0.14','172.16.0.15'])
    session = cluster.connect(keyspace)
    
    sql = "INSERT INTO %s (uid, createtime, score, roomId, imgMeta) VALUES (uuid(), unixTimestampOf(now()), %s, '%s', %s)" % (columnFamily, score, roomId, imgInfo)
    session.execute(sql)
    return

def ResizeImage2(original_file_name):
    x_max_size = 1024
    y_max_size = 1024
    img = Image.open(original_file_name)
    if img.size[0] * img.size[1] > x_max_size * y_max_size:
        x_ratio = img.size[0] / x_max_size
        y_ratio = img.size[1] / y_max_size
        if x_ratio > y_ratio:
            resize_ratio = x_ratio
        else:
            resize_ratio = y_ratio
        resized_x = int(img.size[0] / resize_ratio)
        resized_y = int(img.size[1] / resize_ratio)
        img_resize = img.resize((resized_x, resized_y))
        img_resize.save(original_file_name + '.png')
        return original_file_name + '.png', (resized_x, resized_y)
    else:
        img_resize = img.resize((img.size[0], img.size[1]))
        img_resize.save(original_file_name + '.png')
        return original_file_name + '.png', img.size 

def ResizeImage(original_file_name):
    img = Image.open(original_file_name)
    img_resize = img.resize((1024, 1024))
    img_resize.save(original_file_name + '.png')
    return original_file_name + '.png', img.size

def AngleScoreCalculation(angles):
    answer = {}
    #answer['roll'] = -6.538738250732422 
    #answer['pan']  = 11.67092514038086
    #answer['tilt'] =-11.563632011413574 

    #### for Google
    answer['roll'] = -27.5
    answer['pan']  =  -8.5
    answer['tilt'] =  0
    
    #### For CloudDays
    #answer['roll'] = -10.6
    #answer['pan']  =  13.8
    #answer['tilt'] =  0
    score = (1 - math.sqrt(
                              (
                                  ( (answer['roll'] - angles['roll']) / (45 + abs(answer['roll'])) ) ** 2 +
                                  ( (answer['pan']  - angles['pan'])  / (45 + abs(answer['pan'] )) ) ** 2 +
                                  ( (answer['tilt'] - angles['tilt']) / (45 + abs(answer['tilt'])) ) ** 2
                              )
                          ) / 3
            ) * 100
    #score = int(score * 100)/100
    return score ### returns 100 when same angle

def SmileScoreCalculation(asmile, aemotion):
    total_asmile = 0
    total_asmile -= asmile
    total_asmile -= aemotion['happiness']
    total_asmile += aemotion['anger']
    total_asmile += aemotion['contempt']
    total_asmile += aemotion['disgust']
    #total_asmile += aemotion['fear']
    total_asmile += aemotion['neutral']
    total_asmile += aemotion['sadness']
    #total_asmile += aemotion['surprise'])
    total_asmile = total_asmile / 7.0 * 100
    return total_asmile

'''obsoleted
def SmileScoreCalculation2(asmile, aemotion):
    total_asmile = 10 * (- asmile - aemotion['happiness']
                        + aemotion['anger'] + aemotion['contempt'] + aemotion['disgust'] + aemotion['fear'] + aemotion['neutral'] * 2 + aemotion['sadness'] + aemotion['surprise'])
    return total_asmile
'''

def ImageScoreCalculation(aimage_results):
    aimage_score = 0
    for i in aimage_results['description']['tags']:
        if i == 'curry':
            aimage_score = aimage_score + 2.0
        if i == 'bowl':
            aimage_score = aimage_score + 2.0 
        if i == 'plate':
            aimage_score = aimage_score + 2.0
        if i == 'food':
            aimage_score = aimage_score + 2.0
        if i == 'rice':
            aimage_score = aimage_score + 2.0
    return aimage_score

def AzureImageScoreCalculation(aimage_results, roomId):
    aimage_score = 0.0
    Defined_roomId = {}
    Defined_roomId['Spark Dev Test']     = 'Y2lzY29zcGFyazovL3VzL1JPT00vOTJjZWJiMTAtYmEzZS0xMWU3LWJhMjAtOGZmY2U5ZDgxYzI5'
    Defined_roomId['Prototype']          = 'Y2lzY29zcGFyazovL3VzL1JPT00vYzNiYzk5MTAtMGU1Yi0xMWU4LThhZDAtN2I3MzdlODljMGFl'
    Defined_roomId['RetailTech2018demo'] = 'Y2lzY29zcGFyazovL3VzL1JPT00vOGZlM2NiNjAtMWI3ZS0xMWU4LTg2ODItNzkzMzkyMmFiYTU1'
    Defined_roomId['Prototype2']         = 'Y2lzY29zcGFyazovL3VzL1JPT00vYzA1Yzc3ZDAtMWMzNS0xMWU4LWIzODktOGJhZjRmOGM5NzZj'
    Defined_roomId['smartcoffee']         = 'Y2lzY29zcGFyazovL3VzL1JPT00vM2IzM2E3MTAtYWE5NS0xMWU4LTlhZGUtODkyYzI3NGExN2E2'
    if roomId == Defined_roomId['Prototype']:
        answer_clouddays = ['curry', 'bowl', 'plate', 'food', 'rice', 'meat']
        for ans in answer_clouddays:
            if ans in aimage_results['description']['tags']:
                aimage_score = aimage_score + 2.0
    elif roomId == Defined_roomId['RetailTech2018demo']:
        answer_clouddays = ['fruit', 'bowl', 'glass', 'food', 'topped']
        for ans in answer_clouddays:
            if ans in aimage_results['description']['tags']:
                aimage_score = aimage_score + 2.0
    elif roomId == Defined_roomId['Prototype2']:
        answer_clouddays = ['fruit', 'cake', 'dessert', 'cream', 'topped', 'decorated', 'oranges', 'ice', 'bowl', 'plate']
        for ans in answer_clouddays:
            if ans in aimage_results['description']['tags']:
                aimage_score = aimage_score + 1.2
    return aimage_score

#def TotalScoreCalculation(angle_scores, emotion_scores, object_score): ###remove oboject_score for GoogleNext2018
def TotalScoreCalculation(angle_scores, emotion_scores):
    gtotal = 0.0
    gavg = 50.0
    app.logger.debug("angle Scores List:%s" % (prettyJSON(angle_scores)))
    for angle_score in angle_scores:
        gtotal += angle_score
    if len(angle_scores) != 0:
        gavg = gtotal/len(angle_scores)

    atotal = 0.0
    aavg = 50
    app.logger.debug("emotion Scores List:%s" % (prettyJSON(emotion_scores)))
    for score in emotion_scores:
        atotal += score
    if len(emotion_scores) != 0:
        aavg = atotal/len(emotion_scores)

    final_score = 0.8 * gavg + 0.5 * aavg
    return final_score

app = Flask(__name__)

@app.route("/targeturl", methods = ["GET", "POST"])
def targeturl():
    if request.method == "POST":
        messageId = request.json["data"]["id"]
        roomId    = request.json["data"]["roomId"]
        if debug_mode:
            spark_message = "messageId is:{0}, roomId is:{1}".format(messageId, roomId)
            CiscoSparkPostMessage(spark_message, roomId)

        app.logger.debug('receive Message')
        #spark_message = "resize {0}".format(got_message)
        #CiscoSparkPostMessage(spark_message, roomId)
        #
        #if CiscoSparkGetMessage(messageId)["text"] = 'debug on':
        #if not CiscoSparkGetMessage(messageId)["text"] = '':
        #    debug_mode = True
        #    spark_message = "Debug mode = {0}".format(debug_mode)
        #    CiscoSparkPostMessage(spark_message, roomId)
        #else if CiscoSparkGetMessage(messageId)["text"] = 'debug off':
        #    debug_mode = False
        #    spark_message = "Debug mode = {0}".format(debug_mode)
        #    CiscoSparkPostMessage(spark_message, roomId)
        app.logger.debug("Message ID: %s" % messageId)
        app.logger.debug(prettyJSON(CiscoSparkGetMessage(messageId)))
        file_url = ""
        try:
            file_url  = CiscoSparkGetMessage(messageId)["files"][0]
            app.logger.debug(file_url)
        except:
            app.logger.debug("File Not Found")
            return ('', 204)
        
        original_file_name = CiscoSparkGetContent(file_url)
        file_name, resized = ResizeImage2(original_file_name)
        #if debug_mode:
            #spark_message = "Image size = {0}".format(resized)
            #CiscoSparkPostMessage(spark_message, roomId)
        # GCP
        '''
        gvision_results = GoogleCloudPlatformVisionAPI(file_name)
        gangles = {}
        gscore = []
        for gvision_result in gvision_results:
            gangles['roll'] = gvision_result.roll_angle
            gangles['pan']  = gvision_result.pan_angle
            gangles['tilt'] = gvision_result.tilt_angle
            gscore_this_time = AngleScoreCalculation(gangles)
            spark_message = "angles = {0}, Your GCP score is = {1}".format(str(gangles), str(gscore_this_time))
            CiscoSparkPostMessage(spark_message, roomId)
            gscore.append(gscore_this_time)
        '''
        
        # Azure Image Recognition
        aimage_results = Azure.ImageRecognition(file_name)
        aimage_score = AzureImageScoreCalculation(aimage_results, roomId)
        if debug_mode:
            spark_message = "Azure Item score is = {0}".format(aimage_results['description']['tags'])
            #spark_message = "Azure Item score is = {0}".format(aimage_score)
            CiscoSparkPostMessage(spark_message, roomId)
            spark_message = prettyJSON(aimage_results)
            CiscoSparkPostMessage(spark_message, roomId)
        
        # Azure Face Recognition
        avision_results = Azure.FaceRecognition(file_name)
        aangles = {}
        ascore = []
        asmilescore = []
        for avision_result in avision_results:
            # angle
            aangles['roll'] = avision_result['faceAttributes']['headPose']['roll']
            aangles['pan'] = avision_result['faceAttributes']['headPose']['yaw']
            aangles['tilt'] = avision_result['faceAttributes']['headPose']['pitch']
            ascore_this_time = AngleScoreCalculation(aangles)
            
            app.logger.debug("Base Face Angle Score: %f" % ascore_this_time)

            # smile
            asmile = avision_result['faceAttributes']['smile']
            aemotion = avision_result['faceAttributes']['emotion']
            asmilescore_this_time = SmileScoreCalculation(asmile, aemotion)
            if debug_mode:
                spark_message = "angles = {0}, smile = {1}, emotion = {2}, Your Azure emotion score is = {3}".format(str(aangles), str(asmile), str(aemotion), str(asmilescore_this_time))
                CiscoSparkPostMessage(spark_message, roomId)
            ascore.append(ascore_this_time)
            asmilescore.append(asmilescore_this_time)
        if debug_mode:
            spark_message = "{0}, {1}, {2}".format(str(ascore), str(asmilescore), str(aimage_score))
            CiscoSparkPostMessage(spark_message, roomId)
        
        #total_score = TotalScoreCalculation(ascore, asmilescore, aimage_score) ###Remove aimage_score for GoogleNext2018
        total_score = TotalScoreCalculation(ascore, asmilescore)
        #total_score = float(int(6000 + 4000 * random.random())) / 100
        spark_message = "あなたのお疲れ度は {0} %です".format(str(int(total_score * 100)/100))
        CiscoSparkPostMessage(spark_message, roomId)
        
        ### Smarter Coffee
        strength = strength_calc(total_score)
        IFTTT_make_coffee(roomId, strength)
        spark_message = CoffeeMessage(strength)
        CiscoSparkPostMessage(spark_message, roomId)

        ### Upload Image
        SwiftstackUploadPhoto(file_name, swift_bucket_name)

        ### Upload Data to Database
        imgInfo = {
            "bucket" : swift_bucket_name,
            "key" : file_name
        }
        #CassandraInsertData(total_score, roomId, imgInfo)
        #query = 'SELECT * FROM ciscoteamsdemo'
        BigQueryInsertData(total_score, roomId, imgInfo, strength)
        RemoveTempFile(file_name)
        return ""
    else:
        user_agent = request.headers.get('User-Agent')
        return "you did HTTP GET using {0},\n and data is ".format(user_agent)

@app.route('/targeturl/logging')                                                                 
def index():                                                                    
    app.logger.debug('debug')
    app.logger.info('info')
    app.logger.warn('warn')
    app.logger.error('error')
    app.logger.critical('critical')

    return "logging" 

if __name__ == "__main__":
    # Only for debugging while developing
    app.run(host='0.0.0.0', debug=True, port=80)
