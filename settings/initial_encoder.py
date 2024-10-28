import cv2
import pickle
import face_recognition
import os
import mysql.connector
from mysql.connector import Error

def create_connection():
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Keita@1234',
            database='aiiovdft_profdux'
        )
        print("Connection to MySQL DB successful for Encoding")
    except Error as e:
        print(f"The error '{e}' occurred while connecting to the database")
    return connection

def insert_student_image(connection, student_id, image_path, face_encoding):
    try:
        cursor = connection.cursor()
        encoding_binary = pickle.dumps(face_encoding) if face_encoding is not None else None
        insert_query = """
        INSERT INTO StudentImages (student_id, image_path, face_encoding)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE face_encoding = VALUES(face_encoding)
        """
        cursor.execute(insert_query, (student_id, image_path, encoding_binary))
        connection.commit()
        cursor.close()
    except Error as e:
        print(f"The error '{e}' occurred while inserting student image or face encoding")

def initialize_student_data():
    folderPath = "./static/Files/Images"
    try:
        imgPathList = os.listdir(folderPath)
    except FileNotFoundError as e:
        print(f"The error '{e}' occurred. Folder not found at path: {folderPath}")
        return
    except Exception as e:
        print(f"An unexpected error occurred while accessing the folder: {e}")
        return

    imgList = []
    studentIDs = []
    connection = create_connection()

    if not connection:
        print("Failed to establish connection. Exiting initialization process.")
        return

    for path in imgPathList:
        try:
            imgPath = os.path.join(folderPath, path)
            img = cv2.imread(imgPath)
            if img is None:
                print(f"Could not read image at path: {imgPath}")
                continue
            imgList.append(img)
            studentID = os.path.splitext(path)[0]
            studentIDs.append(studentID)
            insert_student_image(connection, studentID, imgPath, None)
        except Exception as e:
            print(f"An error occurred while processing image {path}: {e}")

    try:
        encodeListKnown = findEncodings(imgList)
    except Exception as e:
        print(f"Error occurred while encoding images: {e}")
        encodeListKnown = []

    encodeListKnownWithIds = [encodeListKnown, studentIDs]

    try:
        with open("EncodeFile.p", "wb") as file:
            pickle.dump(encodeListKnownWithIds, file)
        print("Encoding file saved successfully.")
    except Exception as e:
        print(f"Error occurred while saving encoding file: {e}")

    for student_id, encoding in zip(studentIDs, encodeListKnown):
        insert_student_image(connection, student_id, None, encoding)

    if connection:
        connection.close()

def findEncodings(images):
    encodeList = []
    for img in images:
        try:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            encode = face_recognition.face_encodings(img)
            if encode:
                encodeList.append(encode[0])
            else:
                print("No face encoding found for the image.")
        except Exception as e:
            print(f"Error occurred while encoding an image: {e}")
    return encodeList
