#!/usr/bin/env python
# -*- coding: utf-8 -*-

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler)
import logging, pickle, requests, json
from threading import Timer

import numpy as np
from datetime import date, timedelta, datetime
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as pyplot
import matplotlib.dates as mdates
import os

APIUrls = {"86": "http://158.49.112.86:8080/", "109": "http://158.49.112.109:8080/",
           "87": "http://158.49.112.87:8080/"}

machines = {"86": "158.49.112.86", "87": "158.49.112.87", "109": "158.49.112.109"}
listOfError = []

API_ERROR_CODE = 20
SENSOR_ERROR_CODE = 30
MACHINE_ERROR_CODE = 40

with open('token.txt', 'r') as f:
    TOKEN = f.read()



logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

keys = ['/hideKeyboard', '/activateKeyboard', '/processAllData', '/getGraphics', '/unsubcribe',
            '/subcribe', '/changeTimeToCheck <Time in seconds>']

init_text = "Hi.\n These are the functions that you can use."
for x in keys:
    init_text += "\n" + "\t" * 4 + x

subcribe = {}
try:
    with open("idchats.txt", 'rb') as fichero:
        subcribe = pickle.load(fichero)
except Exception as e:
    with open("idchats.txt", 'wb') as fichero:
        pickle.dump(subcribe, fichero, 0)
time = 180
bot = None

def Error(code, idSensor=None):
    global bot
    print "Error " + str(code)
    if code in APIUrls.keys():
        listOfError.append((code, {"id": code, "tipo": API_ERROR_CODE, "valor": -1}))
        for id, s in subcribe.iteritems():
            if s is True:
                bot.send_message(id, "Error Servidor Api Caida")
    elif code is SENSOR_ERROR_CODE:
        listOfError.append({"id": code + int(idSensor), "tipo": code, "valor": -1})
        for id, s in subcribe.iteritems():
            if s is True:
                bot.send_message(id, "Error Sensor " + str(idSensor))
    elif code in machines.keys():
        listOfError.append({"id": code + MACHINE_ERROR_CODE, "tipo": MACHINE_ERROR_CODE, "valor": -1})
        for id, s in subcribe.iteritems():
            if s is True:
                bot.send_message(id, "Error Servidor Servidor " + str(code) + " Esta Caido")

def uploadErrors():
    while len(listOfError) is not 0:
        # print listOfError
        x = listOfError[-1]
        success = False
        for k, url in APIUrls.iteritems():
            try:
                print "Intentando subir ", url, x
                requests.post(url, data=json.dumps(x), timeout=1)
                listOfError.pop(-1)
                success = True
                break
            except Exception as e:
                print e
                print "Error al subir ", url, x
                pass
        if success is False:
            break

def typeToText(key):
    return {"1": "Temperatura ambiente",
            "2": "Humedad ambiente",
            "3": "Humedad de la tierra",
            "4": "Luminosidad",
            "5": "AEMET Fecha de actualización",
            "6": "AEMET Localidad",
            "7": "AEMET Provincia",
            "8": "AEMET Temperatura máxima",
            "9": "AEMET Temperatura mínima",
            "10": "AEMET Estado del cielo",
            "11": "AEMET Cota de nieve",
            "12": "AEMET Viento",
            "13": "AEMET Racha",
            "14": "AEMET Temperatura horas",
            "15": "AEMET Sensación térmica máxima",
            "16": "AEMET Sensación térmica mínima",
            "17": "AEMET Sensación térmica",
            "18": "AEMET Humedad",
            "19": "AEMET Humedad máxima",
            "20": "AEMET Humedad mínima",
            "21": "AEMET Temperatura máxima"
            }[key]

def monthToNum(shortMonth):
    return {
        'Jan': '01',
        'Feb': '02',
        'Mar': '03',
        'Apr': '04',
        'May': '05',
        'Jun': '06',
        'Jul': '07',
        'Aug': '08',
        'Sep': '09',
        'Oct': '10',
        'Nov': '11',
        'Dec': '12'
    }[shortMonth]

def doRequest(idSensor=""):
    for k, url in APIUrls.iteritems():
        try:
            return json.loads(requests.get(url + str(idSensor), timeout=5).text)
        except Exception as e:
            Error(k)
            print "Error al obtener datos " + url
    return None

def processDataAndSendGraphics(data, update, text=""):
    global bot
    dictDays = {}
    for dato in data:
        f = dato["fecha"].replace(",", "").split(" ")
        d = datetime.strptime(str(f[3] + "-" + monthToNum(f[2]) + "-" + f[1]),"%Y-%m-%d").date()
        if d not in dictDays.keys():
            dictDays[d] = []
        else:
            dictDays[d].append(dato["valor"])
    for k, v in dictDays.iteritems():
        dictDays[k] = np.mean(v)
    # listDates = [datetime.strptime(x, "%Y-%m-%d").date() for x in dictDays.keys()]
    # listDates = dictDays.keys()
    d1 = min(dictDays.keys())
    # d2 = max(listDates)
    d2 = datetime.date(datetime.now())
    delta = d2 - d1
    for i in range(delta.days + 1):
        d = d1 + timedelta(days=i)
        if d not in dictDays.keys():
            dictDays[d] = 0
    lists = sorted(dictDays.items())  # sorted by key, return a list of tuples
    # print lists
    x, y = zip(*lists)  # unpack a list of pairs into two tuples
    pyplot.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y'))
    pyplot.plot(x, y)
    pyplot.gcf().autofmt_xdate()
    pyplot.title(text)
    # pyplot.show()
    pyplot.xticks(rotation=90)
    pyplot.savefig('/tmp/photo.png')
    pyplot.close()
    with open('/tmp/photo.png', 'rb') as photo:
        bot.send_photo(update.message.chat_id, photo)

def processData():
    # Get ids sensors
    sensors = doRequest()
    if sensors is not None:
        average = {}
        lastValue = {}
        for sensor in sensors:
            acum = 0
            if sensor["id"] in [1, 2, 3, 4]:  # Procesar Sensores Jardin
                data = doRequest(sensor["id"])
                for d in data:
                    acum += d["valor"]
                average[sensor["id"]] = acum / len(data)
                lastValue[sensor["id"]] = data[-1]
            else:  # Procesar AEMET
                pass
        text = ""
        for sensor in sensors:
            if sensor["id"] in [1, 2, 3, 4]:
                text += typeToText(str(sensor["id"])) + "\n"
                text += "\t\t\tValor Medio: " + str(average[sensor["id"]]) + "\n"
                text += "\t\t\tUltimo Valor tomado:" + "\n"
                text += "\t\t\t\t\tFecha:" + str(lastValue[sensor["id"]]["fecha"]) + "\n"
                # text += "\t\t\t\t\tid   :" + str(lastValue[sensor["id"]]["id"]) + "\n"
                # text += "\t\t\t\t\ttipo :" + str(lastValue[sensor["id"]]["tipo"]) + "\n"
                text += "\t\t\t\t\tValor:" + str(lastValue[sensor["id"]]["valor"]) + "\n"
        return text
    else:
        return "Error al conectar con la Api"

def SendGraphics(bot, update):
    # Get ids sensors
    sensors = doRequest()
    if sensors is not None:
        sensors = sorted(sensors, key=lambda x: x["id"])
        for sensor in sensors:
            bot.send_message(update.message.chat_id, "Procesando datos con id: " + str(sensor["id"]))
            if sensor["id"] in [1, 2, 3, 4]:  # Procesar Sensores Jardin
                data = doRequest(sensor["id"])
                if data is not None:
                    processDataAndSendGraphics(data, update, "Sensor: " + str(sensor["id"]))
                else:
                    bot.send_message(update.message.chat_id, "Error Api no responde ")
            elif sensor["id"] in [31, 32, 33, 34]:
                data = doRequest(sensor["id"])
                if data is not None:
                    processDataAndSendGraphics(data, update,
                                               "Errores del Sensor: " + str(sensor["id"] - SENSOR_ERROR_CODE))
                else:
                    bot.send_message(update.message.chat_id, "Error Api no responde ")
            elif sensor["id"] in APIUrls.keys():
                data = doRequest(sensor["id"])
                if data is not None:
                    processDataAndSendGraphics(data, update, "Errores de la API: " + str(sensor["id"]))
                else:
                    bot.send_message(update.message.chat_id, "Error Api no responde ")
            else:
                # Procesar AEMET
                pass
    else:
        bot.send_message(update.message.chat_id, "Error Api no responde ")

def handle_start(bot, update):
    if update.message.chat_id not in subcribe.keys():
        subcribe[update.message.chat_id] = True
        print subcribe
        with open("idchats.txt", 'wb') as fichero:
            pickle.dump(subcribe, fichero, 0)
    bot.send_message(update.message.chat_id, init_text)

def handle_help(bot, update):
    bot.send_message(update.message.chat_id, init_text)

def handle_ProcessAllData(bot, update):
    reply_keyboard = [['/hideKeyboard'], ['/processAllData', '/getGraphics'], ['/unsubcribe',
            '/subcribe'], ['/changeTimeToCheck <Time in seconds>']]
    bot.send_message(update.message.chat_id, processData(), reply_markup=ReplyKeyboardMarkup(reply_keyboard))

def handle_GetGraphics(bot, update):
    Timer(1, lambda: SendGraphics(bot, update)).start()

def handle_ActivateKeyboard(bot, update):
    reply_keyboard = [['/hideKeyboard'], ['/processAllData', '/getGraphics'], ['/unsubcribe',
            '/subcribe'], ['/changeTimeToCheck <Time in seconds>']]
    bot.send_message(update.message.chat_id, "ActivateKeyboard", reply_markup=ReplyKeyboardMarkup(reply_keyboard))

def handle_HideKeyboard(bot, update):
    bot.send_message(update.message.chat_id, "HideKeyboard", reply_markup=ReplyKeyboardRemove())

def handle_unsubcribe(bot, update):
    subcribe[update.message.chat_id] = False
    with open("idchats.txt", 'wb') as fichero:
        pickle.dump(subcribe, fichero, 0)

def handle_subcribe(bot, update):
    subcribe[update.message.chat_id] = True
    with open("idchats.txt", 'wb') as fichero:
        pickle.dump(subcribe, fichero, 0)

def handle_ChangeTimeToCheck(bot, update):
    global time
    try:
        time = int(update.message.text.split(" ")[1])
        bot.send_message(update.message.chat_id, "Time changed to " + str(time))
    except:
        bot.send_message(update.message.chat_id, "Error\n The command should be /ChangeTimeToCheck <Time in seconds>")


# def echo_all(bot, update):
#     print message
#     bot.send_message(update.message.chat_id, "I don't know what you mean.\n" + init_text)

    # bot.send_message(update.message.chat_id, "ActiveKeyboard", reply_markup=mainKeyBoard)




def checkMachines():
    for k, ip in machines.iteritems():
        response = os.system("ping -c 1 " + ip)
        if response is not 0:
            Error(k)


def checkSystem():
    global time
    Timer(time, checkSystem).start()
    # checkMachines()
    sensors = doRequest()
    if sensors is not None:
        for sensor in sensors:
            if sensor["id"] in [1, 2, 3, 4]:  # Procesar Sensores Jardin
                data = doRequest(sensor["id"])
                if data is not None:
                    list_days = []
                    for d in data:
                        f = d['fecha'].split(",")[1].replace(" GMT", "")[1:]
                        d = datetime.strptime(f, "%d %b %Y %H:%M:%S")
                        list_days.append(d)
                    last_date = max(list_days)
                    now = datetime.now()
                    if now + timedelta(minutes=-15) > last_date:
                        Error(SENSOR_ERROR_CODE, sensor["id"])
            else:
                # Procesar AEMET
                pass
    uploadErrors()

def main():
    global bot
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)
    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", handle_start))
    dp.add_handler(CommandHandler("help", handle_help))
    dp.add_handler(CommandHandler("processAllData", handle_ProcessAllData))
    dp.add_handler(CommandHandler("getGraphics", handle_GetGraphics))
    dp.add_handler(CommandHandler("activateKeyboard", handle_ActivateKeyboard))
    dp.add_handler(CommandHandler("hideKeyboard", handle_HideKeyboard))
    dp.add_handler(CommandHandler("unsubcribe", handle_unsubcribe))
    dp.add_handler(CommandHandler("subcribe", handle_subcribe))
    dp.add_handler(CommandHandler("changeTimeToCheck", handle_ChangeTimeToCheck))

    # log all errors
    # dp.add_error_handler(error)
    bot = updater.bot

    # Start the Bot
    Timer(1, updater.start_polling).start()
    checkSystem()
    # updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    # updater.idle()


if __name__ == '__main__':
    main()