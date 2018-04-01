#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include "DHT.h"

#define DHTPIN D4     // what digital pin the DHT22 is conected to
#define DHTTYPE DHT22   // there are multiple kinds of DHT sensors

DHT dht(DHTPIN, DHTTYPE);

const char* ssid = "NotebookNet";
const char* password = "0660101327";

ESP8266WebServer server(80);

const int led = 13;
const int r1 = D8;
const int r2 = D7;

void handleRoot() {
  digitalWrite(led, 1);
  server.send(200, "text/plain", "hello from esp8266!");
  digitalWrite(led, 0);
}

void handleNotFound(){
  digitalWrite(led, 1);
  String message = "File Not Found\n\n";
  message += "URI: ";
  message += server.uri();
  message += "\nMethod: ";
  message += (server.method() == HTTP_GET)?"GET":"POST";
  message += "\nArguments: ";
  message += server.args();
  message += "\n";
  for (uint8_t i=0; i<server.args(); i++){
    message += " " + server.argName(i) + ": " + server.arg(i) + "\n";
  }
  server.send(404, "text/plain", message);
  digitalWrite(led, 0);
}

void send_status(){
    int r1_status = digitalRead(r1);
    int r2_status = digitalRead(r2);
    server.send(200, "application/json", "{\"1\":" + String(r1_status) + ", \"2\":" + String(r2_status) + "}");
}

void setup(void){
  Serial.println("setup");
  pinMode(led, OUTPUT);
  pinMode(r1, OUTPUT);
  pinMode(r2, OUTPUT);
  digitalWrite(led, 0);
  digitalWrite(r1, 0);
  digitalWrite(r2, 0);
  
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
//  IPAddress ip(192, 168, 1, 101); // where xx is the desired IP Address
//  IPAddress gateway(192, 168, 1, 1); // set gateway to match your network
//  Serial.print(F("Setting static ip to : "));
//  Serial.println(ip);
//  IPAddress subnet(255, 255, 255, 0); // set subnet mask to match your
//  WiFi.config(ip, gateway, subnet);
  
  WiFi.begin(ssid, password);
  Serial.println("");
  Serial.println("done");

  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  if (MDNS.begin("esp8266")) {
    Serial.println("MDNS responder started");
  }

  server.on("/", handleRoot);

  server.on("/test", [](){
    server.send(200, "text/plain", "this works as well");
  });

  server.on("/on", [](){
    String relay=server.arg("relay");
    if (relay == "1")  digitalWrite(r1, 1);
    if (relay == "2")  digitalWrite(r2, 1);
    int r1_status = digitalRead(r1);
    int r2_status = digitalRead(r2);
    send_status();
  });

  server.on("/off", [](){
    String relay=server.arg("relay");
    if (relay == "1")  digitalWrite(r1, 0);
    if (relay == "2")  digitalWrite(r2, 0);
    send_status();
  });

  server.on("/status", [](){
    send_status();
  });

  server.on("/air_temperature", [](){
    delay(2000);
    float h = dht.readHumidity();
    // Read temperature as Celsius (the default)
    float t = dht.readTemperature();
    server.send(200, "application/json", "{\"temp\":" + String(t) + ", \"hum\":" + String(h) + "}");
  });

  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("HTTP server started");
}

void loop(void){
  server.handleClient();
}

