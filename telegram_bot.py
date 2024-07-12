import requests
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from wordpress_xmlrpc.compat import xmlrpc_client
from wordpress_xmlrpc.methods import media
from telegram.ext import Updater, Filters , MessageHandler
import logging
import traceback
from telegram import Bot
import mimetypes
import os
import subprocess


#-------------------------------------------------------------------------------------
#Saving log of the program
log_file_path = 'log_file.log'  # Replace with the actual path
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

def save_log(content):
    logging.info('(Script Log) > '+content)
#------------------------------------------------------------------------------------------

try: #creating a try loop to extract all errors and log it.
# Set up your Telegram bot and WordPress credentials
    telegram_bot_token = 'YOUR TELEGRAM BOT TOKEN'
    wordpress_endpoint = 'https:/YOURWEBSITE.COM/xmlrpc.php' #endpoint for xmlrpc lib
    media_endpoint = 'https://YOURWEBSITE.COM//wp-json/wp/v2/media' #endpoint for Rest API
    wordpress_username = 'your username'
    wordpress_password = 'your password'
    application_password = 'your application password'
    parent_page_id = 0000  # Replace with the ID of your specific parent page
    session = requests.Session() #creating a session for REST API
    session.auth = (wordpress_username, application_password) #authenticating using application password
# Initialize the WordPress client
    wp = Client(wordpress_endpoint, wordpress_username, wordpress_password)

#funcltion to find file extention and write the file in local dir
    def file_extn(file_url): #funcltion to find file extention
        save_log('running > File extenstion retrival system')
    # Send a HEAD request to get the file's metadata, including content type
        response = session.head(file_url)

        if response.status_code == 200:
            # Get the content type (MIME type) from the response headers
            content_type = response.headers.get('content-type')
            if content_type:
                # Use the content type to determine the file extension
                file_extension = mimetypes.guess_extension(content_type)
                mime_type = content_type
            else:
                # If content type is not available, use a default extension
                file_extension = '.jpg'  # You can change this to your preferred default
                mime_type = 'image/jpeg'
                 # Generate a file name based on a timestamp or a unique identifier
            file_name = 'media' + file_extension

            # Download the file and save it with the generated name
            with open(file_name, 'wb') as f:
                response = session.get(file_url)
                f.write(response.content)
            save_log(f'file mime type found - {mime_type} & file written to local dir')
            return file_name, mime_type
        else:
            save_log(f'Failed to find mime type - file not written in local dir!')
            return None

    #code to upload file with REST api 
    def upload_file(file_path,mime_type = 'image/jpeg'):
        # Open and read the file in binary mode
        with open(file_path, 'rb') as file:
            # Create a WordPress media item
            media_data = {
                'name': file_path,
                'type': mime_type,}

            # Upload the media item
            response = session.post(media_endpoint , data = media_data, files = {'file': (file_path,file)})
            if response.status_code in (200,201):
                # Media was successfully uploaded
                media_info = response.json()
                media_url = media_info['guid']['rendered']
                save_log(f'Media URL: {media_url} - Media id : {media_id}')
                os.remove(file_path)
                save_log(f'FILE {file_path} removed successfully')
                return media_url
            else:
                save_log(f'Failed to upload media to WordPress. Status code: {response.status_code} - {response.text}')
                return None
    #function to create wordpress post
    def create_wordpress_post(media_url, caption, is_video=False):
        post = WordPressPost()
        post.title = caption[:50]  # Use the caption as the post title (limit to 50 characters)

        # Generate HTML content for previews
        if is_video:
            # For videos, add a play button
            post.content = f'<video controls><source src="{media_url}" type="video/mp4">Your browser does not support the video tag.</video>'
        else:
            # For photos, display the image
            post.content = f'<img src="{media_url}" alt="{caption}">'

        post.post_status = 'publish'
    
        post.post_parent = parent_page_id  # Set the parent page ID

        # Publish the post
        post_id = wp.call(NewPost(post))
        return post_id

    def create_vd_thmbnail(video_path):
        # Generate a thumbnail for the video
        thumbnail_filename = 'thumbnail.jpg'
        thumbnail_command = [
            'ffmpeg', '-i', video_path, '-ss', '00:00:05', '-vframes', '1', thumbnail_filename]

        try:
            subprocess.run(thumbnail_command, check=True, stderr=subprocess.PIPE)
            save_log(f'thumbnail successfully create with file name: {thumbnail_filename}')
            return thumbnail_filename
        except subprocess.CalledProcessError as e:
            save_log(f"Error creating video thumbnail: {e.stderr.decode()}")
            thumbnail_filename = None
            return thumbnail_filename

    # Define a function to handle incoming messages (e.g., photos and videos)
    def handle_message(update, context):
        message = update.message
        save_log(f'Messages>> {message}')
        if message.photo:
            # Handle photo messages
            photo = message.photo[-1]  # Use the largest photo
            file_name, mime_type = file_extn(photo.file_id) #gets the file extension , mime type and writes the file to the local dir
            media_file_id = upload_file(file_name,mime_type) #uploads the file to wordpress lib with local dir loc
            caption = message.caption or ''

            # Create a WordPress post for photos
            post_id = create_wordpress_post(media_file_id, caption)

            save_log(f'Created WordPress post with ID {post_id}')

        if message.video:
        # Handle video messages
            video = message.video
            file_name, mime_type = file_extn(video.file_id) #gets the file extension , mime type and writes the file to the local dir
            thmb_file = create_vd_thmbnail(file_name) #creates a thumbnail file for video
            thmb_url = upload_file(thmb_file, 'image/jpeg') #uploads the thumbnail file to wordpress lib
            media_file_id = upload_file(file_name , mime_type)#uploads the  video file to wordpress lib with local dir loc
            caption = message.caption or ''

        # Create a WordPress post for videos
            post_id = create_wordpress_post(media_file_id, caption, is_video=True)

            save_log(f'Created WordPress post with ID {post_id}') 

    # Set up your Telegram bot and add the message handler
    boT = Bot(token=telegram_bot_token) #creates a bot instance
    updater = Updater(bot=boT, use_context=True) #initializes the updater for bot 
    dispatcher = updater.dispatcher
    message_handler = MessageHandler(Filters.all, handle_message)
    dispatcher.add_handler(message_handler)
    save_log(f'Bot setup completed - Message handler Activated.')

# Start the bot
    updater.start_polling()
    save_log(f'Message Polling Active')
    updater.idle()


except Exception as er:
    msg = traceback.format_exc()
    save_log(f'Error occured: {er}')
    save_log(f'Traceback: {msg}')
    save_log(f'\n------------ TERMINATING SESSION DUE TO THE ABOVE ERROR -------------')
