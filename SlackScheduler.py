# Copyright 2023 UNREAL SOFTWARE ORG.
#
# The corresponding source code is free: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# This Python script and corresponding source code is distributed 
# in the hope that it will be useful, but with permitted additional restrictions
# under Section 7 of the GPL. See the GNU General Public License in LICENSE.TXT
# distributed with this program. You should have received a copy of the
# GNU General Public License along with permitted additional restrictions
# with this program. If not, see <https://github.com/GeorgeAlex-M/SlackScheduler>

# $Header: /SlackScheduler/SlackScheduler.py 3     01/08/23 2:35p George $
###################################################################################################
#                        C O N F I D E N T I A L  ---  U N R E A L  S O F T W A R E               #
###################################################################################################
#                                                                                                 #
#                    Project Name : Slack Scheduler                                               #
#                                                                                                 #
#                       File Name : SlackScheduler.py                                             #
#                                                                                                 #
#                      Programmer : George Manea                                                  #
#                                                                                                 #
#                      Start Date : 01/04/23                                                      #
#                                                                                                 #
#                     Last Update : 27/02/24                                                      #
#                                                                                                 #
#-------------------------------------------------------------------------------------------------#
# Functions:                                                                                      #
#   SlackScheduler.__init__ -- Initializes the SlackScheduler with a Slack API token.             #
#   SlackScheduler.clear_schedule -- Clears all scheduled tasks in the scheduler.                 #
#   SlackScheduler.convert_to_24h_format -- Converts time from 12-hour to 24-hour format.         #
#   SlackScheduler.current_time_str -- Gets the current time as a formatted string.               #
#   SlackScheduler.log_message -- Logs a message with a timestamp and action.                     #
#   SlackScheduler.get_user_id -- Retrieves the user ID for a given username from Slack.          #
#   SlackScheduler.send_message -- Sends a message to a specified Slack channel.                  #
#   SlackScheduler.schedule_shift_reminders -- Schedules reminders for a specific shift type.     #
#   SlackScheduler.scheduled_message_sender -- Returns a function that sends a scheduled message. #
#   SlackScheduler.schedule_meeting_on_day -- Schedules a meeting reminder on a specific day.     #
#   SlackScheduler.schedule_meeting_reminders -- Schedules all meeting reminders based on config. #
#   SlackScheduler.listen_for_commands -- Listens for commands from the user input.               #
#   SlackScheduler.send_to_channel -- Sends a message to a specific Slack channel.                #
#   SlackScheduler.run -- Starts the Slack scheduler, executing scheduled tasks and commands.     #
#                                                                                                 #
#   CommandHandler.__init__ -- Initializes the CommandHandler with a reference to the scheduler.  #
#   CommandHandler.handle_command -- Processes incoming commands and executes actions.            #
#-------------------------------------------------------------------------------------------------#
# Class Descriptions:                                                                             #
#   SlackScheduler - Manages Slack scheduling and message automation tasks.                       #
#   CommandHandler - Processes incoming commands and directs them to the SlackScheduler.          #
#-------------------------------------------------------------------------------------------------#
# Detailed Description:                                                                           #
#   This Python script, SlackScheduler.py, automates various scheduling and messaging tasks on    #
#   Slack. It sends shift reminders, meeting notifications, and handles custom commands for       #
#   message delivery. Utilizing the Slack API, it communicates with Slack channels and manages    #
#   interactions. The script features a dynamic configuration system, supporting different types  #
#   of shifts such as day, night, weekend, and overtime.                                          #
#-------------------------------------------------------------------------------------------------#

import threading
import re
import schedule
import time
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class CommandHandler:
    def __init__(self, scheduler):
        self.scheduler = scheduler

    # ------------------------------------------------------------------------------------------
    # Function: handle_command
    # Description: Processes incoming commands and directs them to the appropriate action.
    #              Supports commands for sending messages to specific channels.
    #
    # Parameters:
    #   command (str): The command string to be processed.
    # 
    # Example usage:
    #   General channel - /w C043NCYSH1V Good luck @george! :ah-ha-nya:
    #   Private channel - /w C06CF9GUG8K Good luck @george! :ah-ha-nya:
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def handle_command(self, command):
        command = command.strip()
        components = command.split(" ")
        cmd = components.pop(0)

        # Early checks for specific commands
        if cmd == "help":
            if components:
                self.display_help_for_command(components[0])
            else:
                available_commands = ", ".join(self.scheduler.config["commands"].keys())
                print(f"You have to select a command to display the help for. The current commands are: {available_commands}")
            return

        channel_id = None  # Initialize channel_id
        message = []  # Use a list to collect message components for easier manipulation

        # Loop through components to process switches and construct the message
        i = 0  # Index for manual loop control
        while i < len(components):
            if components[i] == "-C" and (i + 1) < len(components):
                channel_id = components[i + 1]  # Assign the next component as the channel_id
                i += 2  # Skip the next component as it's already processed as channel_id
            else:
                message.append(components[i])
                i += 1

        message_text = " ".join(message).strip()  # Convert message list back to a string

        if cmd == "/w":
            if not channel_id:
                channel_id = self.scheduler.config["commands"].get(cmd, {}).get("default_channel", None)
            
            if channel_id and message_text:
                self.scheduler.send_to_channel(channel_id, message_text)
            else:
                print("You must specify a channel (-C channel_id) and a message to send.")
        else:
            print(f"Unrecognized or unsupported command: {cmd}. Use 'help' to see available commands.")

    def display_help_for_command(self, cmd):
        # Fetch the command configuration
        cmd_config = self.scheduler.config["commands"].get(cmd)
        
        if cmd_config:
            # Display the description and usage instructions
            print(f"Help for '{cmd}':\n{cmd_config['description']}")
            for switch, details in cmd_config.get("switches", {}).items():
                print(f"  {switch}: {details['description']}")
        else:
            # Inform the user if the specified command does not exist
            print(f"No help available for: {cmd}")


class SlackScheduler:
    config = {
        "enable_features": {
            "day_shift": True,
            "night_shift": True,
            "weekend_shift": True,
            "overtime_shift": True,
            "meeting_reminders": False,
            "random_messages": False
        },
        "commands": {
            "help": {
                "description": "Provides usage information for a specified command. For example, 'help /w' displays help for the '/w' command.",
            },
            "/w": {
                "description": "Send a message to a specified channel. Use -C to specify the channel ID.",
                "default_channel": "C043NCYSH1V",  # Replace with your actual default channel ID
                "switches": {
                    "-C": {
                        "description": "Specify the channel ID where the message will be sent. For example, '/w -C C043NCYSH1V Good morning!' sends 'Good morning!' to channel C043NCYSH1V."
                    }
                }
            }
            # Additional commands can be configured here with similar structure
        },
        "shift_message_config": {
            "day_shift": {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "messages": {
                    "09:00 AM": "Good morning, team. Let's commence our cybersecurity tasks for the day.",
                    "11:15 AM": "Reminder: Short break from 11:15 to 11:30. Please take a moment to rest.",
                    "11:30 AM": "Break time is over. Please continue with your scheduled cybersecurity activities.",
                    "01:00 PM": "Lunch break from 13:00 to 14:00. Remember to step away from your workstations.",
                    "02:00 PM": "Lunch break has ended. Resume your cybersecurity responsibilities.",
                    "04:00 PM": "Scheduled break from 16:00 to 16:15. A brief pause for regrouping.",
                    "04:15 PM": "Break time has concluded. Please proceed with your tasks.",
                    "05:00 PM": "End of day's shift. Ensure your work is properly saved and secured."
                }
            },
            "night_shift": {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "messages": {
                    "06:30 PM": "Night shift commences. Teams are to remain vigilant.",
                    "08:00 PM": "Scheduled break from 20:00 to 20:15. Please take this time to relax.",
                    "08:15 PM": "Break has ended. Resume night-time cybersecurity operations.",
                    "09:00 PM": "Mid-shift break from 21:00 to 21:15. Use this time to recharge.",
                    "10:00 PM": "Continue with night shift duties. Maintain focus and diligence.",
                    "12:00 AM": "Short break from 00:00 to 00:15. Stay alert and prepared.",
                    "12:15 AM": "Resume night shift activities until the end of the shift.",
                    "02:00 AM": "Night shift concludes. Ensure all tasks are completed before logging off."
                }
            },
            "weekend": {
                "days": ["saturday", "sunday"],
                "messages": {
                    "11:00 AM": "Weekend operations start now. Dedication to tasks is essential.",
                    "01:00 PM": "Lunch break from 13:00 to 14:00. Take this time for a proper meal.",
                    "02:00 PM": "Resume weekend duties. Focus on completing all scheduled activities.",
                    "04:00 PM": "Take a brief break from 16:00 to 16:15. Reflect on tasks completed.",
                    "04:15 PM": "Continue with the remaining tasks for the weekend.",
                    "05:00 PM": "Weekend operations conclude. Ensure all activities are logged appropriately."
                }
            },
            "overtime": {
                "days": ["saturday", "sunday"],
                "messages": {
                    "02:00 AM": "Overtime shift begins. Please concentrate on pending tasks.",
                    "03:30 AM": "Short break from 03:30 to 03:45. Use this time to rest briefly.",
                    "03:45 AM": "Resume overtime work. Prioritize tasks efficiently.",
                    "05:00 AM": "Take a final break from 05:00 to 05:15. Prepare for the last stretch of work.",
                    "05:15 AM": "Continue with the remaining overtime tasks.",
                    "06:00 AM": "Overtime shift ends. Confirm completion of all tasks before logging off."
                }
            }
        },
        "meeting_reminders": {
            # Day shift
            "09:30 AM": {
                "days": ["monday"],
                "message": "9:30 AM – 10:00 AM (Mon) - Cybersecurity Sprint Planning\nMeeting ID: 325 692 613 318\nPasscode: Secure123\nLobby Bypass: People in org and guests"
            },
            "11:15 AM": {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "message": "11:15 AM – 11:30 AM (Every weekday (Mon-Fri)) - Threat Intelligence Briefing\nMeeting ID: 393 725 551 975\nPasscode: ThreatNet\nLobby Bypass: People in org and guests"
            },
            "11:40 AM": {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "message": "11:40 AM – 12:10 PM (Every weekday (Mon-Fri)) - Security Operations Sync-Up\nMeeting ID: 329 721 470 133\nPasscode: OpsSecure\nLobby Bypass: People in org and guests"
            },
            "01:00 PM": {
                "days": ["tuesday"],
                "message": "1:00 PM – 2:00 PM (Tue) - Vulnerability Assessment Review\nMeeting ID: 389 305 352 850\nPasscode: VulnScan\nLobby Bypass: People in org and guests"
            },
            "01:30 PM": {
                "days": ["thursday"],
                "message": "1:30 PM – 2:30 PM (Thu) - Incident Response Team Meeting\nMeeting ID: 371 990 411 935\nPasscode: IRReady\nLobby Bypass: People in org and guests"
            },
            "02:30 PM": {
                "days": ["friday"],
                "message": "2:30 PM – 3:00 PM (Fri) - Weekly Cybersecurity Strategy Session\nMeeting ID: 367 910 333 672\nPasscode: StrategySec\nLobby Bypass: People in org and guests"
            },
            "04:00 PM": {
                "days": ["friday"],
                "message": "4:00 PM – 4:30 PM (Fri) - Security Tooling Sprint Review\nMeeting ID: 318 600 963 564\nPasscode: ToolsRev\nLobby Bypass: People in org and guests"
            },
            "04:30 PM": {
                "days": ["friday"],
                "message": "4:30 PM – 5:00 PM (Fri) - Cybersecurity Retrospective and Look Ahead\nMeeting ID: 389 805 633 508\nPasscode: CyberLook\nLobby Bypass: People in org and guests"
            }
            # Night shift
            
        },
        "random_messages": [
            "🛡️ Every scan, every line of code, fortifies our digital realm.",
            # ... [other random messages]
        ]
    }

    # ------------------------------------------------------------------------------------------
    # Constructor for SlackScheduler
    # Description: Initializes the SlackScheduler with a Slack API token.
    #
    # Parameters:
    #   slack_token (str): The token used for authenticating with the Slack API.
    #
    # Returns: None
    # ------------------------------------------------------------------------------------------
    def __init__(self, slack_token):
        # Initializes WebClient with provided Slack API token
        self.client = WebClient(token=slack_token)
        
        # Creates a CommandHandler instance with a reference to this scheduler
        self.command_handler = CommandHandler(self)
        
        # Clears any previously scheduled tasks upon initialization
        self.clear_schedule()

    # ------------------------------------------------------------------------------------------
    # Function: convert_to_24h_format
    # Description: Converts a time string from 12-hour format to 24-hour format.
    #
    # Parameters:
    #   time_str (str): The time string in 12-hour format (e.g., "02:00 PM").
    #
    # Returns:
    #   str: The time string in 24-hour format (e.g., "14:00").
    # ------------------------------------------------------------------------------------------
    def convert_to_24h_format(self, time_str):
        # Converts a time string from 12-hour format (e.g., '02:00 PM') to 24-hour format (e.g., '14:00')
        return datetime.datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")

    # ------------------------------------------------------------------------------------------
    # Function: current_time_str
    # Description: Gets the current time as a formatted string.
    #
    # Returns:
    #   str: The current time in the format "HH:MM AM/PM".
    # ------------------------------------------------------------------------------------------
    def current_time_str(self):
        # Retrieves the current time and formats it as a string in "HH:MM AM/PM" format
        return datetime.datetime.now().strftime("%I:%M %p")

    # ------------------------------------------------------------------------------------------
    # Function: log_message
    # Description: Logs a message with a timestamp and action.
    #
    # Parameters:
    #   action (str): The action or event that occurred.
    #   message (str): The message to log.
    #
    # Returns: None
    # ------------------------------------------------------------------------------------------
    def log_message(self, action, message):
        # Logs a message with a timestamp and the specified action
        # Useful for tracking events and errors within the application
        print(f"{self.current_time_str()} - {action}: {message}")

    # ------------------------------------------------------------------------------------------
    # Function: get_user_id
    # Description: Retrieves the user ID for a given username from Slack.
    #
    # Parameters:
    #   username (str): The username to look up.
    #
    # Returns:
    #   str or None: The user ID if found, otherwise None.
    # ------------------------------------------------------------------------------------------
    def get_user_id(self, username):
        # Attempts to retrieve a user ID from Slack for a given username
        try:
            # Fetches list of users from Slack
            response = self.client.users_list()
            members = response["members"]
            
            # Searches for the specified username in the members list
            for member in members:
                if 'name' in member and member['name'] == username:
                    # Returns the ID of the user if found
                    return member['id']
        except SlackApiError as e:
            # Logs error if user list retrieval fails
            self.log_message("Error retrieving user list", f"{e.response['error']}")
        return None

    # ------------------------------------------------------------------------------------------
    # Function: send_message
    # Description: Sends a message to a specified Slack channel. It formats the message
    #              by replacing usernames with user IDs and handles any necessary
    #              message formatting.
    #
    # Parameters:
    #   channel_id (str): The ID of the channel where the message will be sent.
    #   message (str): The message to be sent.
    #
    # Returns: None
    #
    # Warnings: Handles SlackApiError if an issue occurs with the Slack API.
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def send_message(self, channel_id, message):
        # Searches for usernames in the message and replaces them with Slack user IDs for proper tagging
        usernames = re.findall(r'@(\w+)(?=\s|\.|!|\/|\W)', message)
        for username in usernames:
            user_id = self.get_user_id(username)
            if user_id:
                # Replaces username with Slack formatted user ID tag
                message = message.replace(f"@{username}", f"<@{user_id}>")
            else:
                # Logs a message if the username could not be resolved to a user ID
                self.log_message("User not found", f"Username @{username} could not be resolved to a user ID.")
        
        # Formatting message to replace "@here" with the appropriate Slack tag
        formatted_message = message.replace("@here", "<!here>")

        # Attempting to send the formatted message to the specified Slack channel
        self.log_message("Attempting to send message", formatted_message)
        try:
            # Sends the message to the specified Slack channel
            response = self.client.chat_postMessage(channel=channel_id, text=formatted_message)
            # Logs the successful message transmission
            self.log_message("HTTP POST", response['message']['text'])
        except SlackApiError as e:
            # Logs an error message if the message sending fails
            self.log_message("Error sending message", f"{e.response['error']}")

    # ------------------------------------------------------------------------------------------
    # Function: clear_schedule
    # Description: Clears all the tasks scheduled in the scheduler. This is typically used
    #              to reset the schedule, removing all previously set reminders and tasks.
    #
    # Parameters: None
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def clear_schedule(self):
        # Clears all scheduled tasks in the scheduler.
        # This function is typically used when needing to reset or update the schedule.
        schedule.clear()

    # ------------------------------------------------------------------------------------------
    # Function: schedule_shift_reminders
    # Description: Schedules shift reminders based on the shift type and sends them to the
    #              specified Slack channel. This includes day, night, weekend, and overtime shifts.
    #
    # Parameters:
    #   shift_type (str): Type of the shift (e.g., "day_shift", "night_shift").
    #   channel_id (str): The ID of the channel where reminders will be sent.
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    
    def schedule_shift_reminders(self, shift_type, channel_id):
        # Check if the shift type is enabled in the configuration
        if not self.config["enable_features"].get(shift_type, False):
            self.log_message("Scheduling", f"{shift_type} is disabled in the config. Skipping scheduling.")
            return

        # Retrieves shift configuration based on the specified shift type (e.g., 'day_shift')
        shift_config = self.config["shift_message_config"].get(shift_type, {})

        # Iterates through each day and message in the shift configuration
        for day in shift_config.get("days", []):
            for time_key, message in shift_config.get("messages", {}).items():
                # Converts time to 24-hour format and schedules the reminder
                converted_time = self.convert_to_24h_format(time_key)
                schedule.every().day.at(converted_time).do(
                    self.scheduled_message_sender(channel_id, message, day))

    # ------------------------------------------------------------------------------------------
    # Function: scheduled_message_sender
    # Description: Creates a function that sends a scheduled message to a specified channel.
    #              This function checks the current day and sends the message if it matches
    #              the specified day.
    #
    # Parameters:
    #   channel_id (str): The ID of the channel where the message will be sent.
    #   message (str): The message to be sent.
    #   day (str): The day of the week when the message should be sent.
    #
    # Returns:
    #   function: A function that sends the message if the day matches.
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def scheduled_message_sender(self, channel_id, message, day):
        # Creates a closure function that sends a message on the specified day
        def send():
            # Checks if the current day matches the specified day for the message
            if datetime.datetime.now().strftime("%A").lower() == day:
                # Sends the message to the specified channel
                self.send_message(channel_id, message)
        return send

    # ------------------------------------------------------------------------------------------
    # Function: schedule_meeting_on_day
    # Description: Schedules a meeting reminder on a specified day of the week.
    #
    # Parameters:
    #   day (str): The day of the week to schedule the meeting.
    #   time (str): The time to send the reminder.
    #   message_sender (function): The function that sends the reminder message.
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def schedule_meeting_on_day(self, day, time, message_sender):
        # Schedules a meeting reminder for a specific day and time
        # The day parameter is the day of the week (e.g., 'monday'), and time is in 24-hour format
        getattr(schedule.every(), day).at(self.convert_to_24h_format(time)).do(message_sender)

    # ------------------------------------------------------------------------------------------
    # Function: schedule_meeting_reminders
    # Description: Schedules all meeting reminders as per the configuration settings.
    #              Reminders are sent to the designated Slack channel on the specified days and times.
    #
    # Parameters:
    #   channel_id (str): The ID of the Slack channel where reminders will be sent.
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def schedule_meeting_reminders(self, channel_id):
        # Check if meeting reminders are enabled in the configuration
        if not self.config["enable_features"]["meeting_reminders"]:
            self.log_message("Scheduling", "Meeting reminders are disabled in the config. Skipping scheduling.")
            return

        # Set to track unique combinations of day and time to prevent duplicate scheduling
        scheduled_times = set()

        # Iterates through the meeting reminders in the configuration
        for time_key, info in self.config["meeting_reminders"].items():
            for day in info["days"]:
                # Creates a message sender function for each meeting reminder
                message_sender = self.scheduled_message_sender(channel_id, info["message"], day)
                schedule_key = f"{day}_{time_key}"

                # Schedules the meeting reminder if it hasn't been scheduled already
                if schedule_key not in scheduled_times:
                    self.schedule_meeting_on_day(day, time_key, message_sender)
                    scheduled_times.add(schedule_key)
                    # Logs the scheduling of the meeting reminder
                    self.log_message("Scheduling", f"Scheduled meeting reminder '{info['message']}' at {time_key} on {day}")

    # ------------------------------------------------------------------------------------------
    # Function: listen_for_commands
    # Description: Continuously listens for user input and processes commands in real-time.
    #
    # Returns: None
    #
    # Warnings: This function runs indefinitely in a loop.
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def listen_for_commands(self):
        # Listens indefinitely for user input and processes any incoming commands
        print("Listening for commands...")
        while True:
            # Waits for user input
            cmd = input()
            # Handles the received command
            self.command_handler.handle_command(cmd)

    # ------------------------------------------------------------------------------------------
    # Function: send_to_channel
    # Description: Sends a message to a specified channel on Slack.
    #              Utilizes the 'send_message' function to handle the message formatting and delivery.
    #
    # Parameters:
    #   channel_id (str): The ID of the Slack channel to send the message to.
    #   message (str): The message to be sent.
    #
    # Returns: None
    #
    # Warnings: None
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def send_to_channel(self, channel_id, message):
        # Sends a message to a specific Slack channel using the existing send_message method
        self.send_message(channel_id, message)

    # ------------------------------------------------------------------------------------------
    # Function: run
    # Description: Initiates the Slack scheduler, starting a thread to listen for commands
    #              and continuously executing scheduled tasks.
    #
    # Returns: None
    #
    # Warnings: This function initiates an infinite loop for listening to commands.
    #
    # History:
    #   01/04/23 - Function created by George Manea
    # ------------------------------------------------------------------------------------------
    def run(self):
        # Initiates the Slack scheduler, running in its own thread to listen for commands
        command_thread = threading.Thread(target=self.listen_for_commands)
        command_thread.daemon = True
        command_thread.start()

        # Continuously checks and executes pending scheduled tasks
        while True:
            schedule.run_pending()
            # Waits for a minute before checking for pending tasks again
            time.sleep(60)

# Example Implementation
# Creating an instance of SlackScheduler with an API key
slack_scheduler = SlackScheduler("Your API Key")

# Scheduling shift reminders for different types of shifts in a specific Slack channel
slack_scheduler.schedule_shift_reminders("day_shift", "Your Channel ID")
slack_scheduler.schedule_shift_reminders("night_shift", "Your Channel ID")
slack_scheduler.schedule_shift_reminders("weekend_shift", "Your Channel ID")
slack_scheduler.schedule_shift_reminders("overtime_shift", "Your Channel ID")

# Scheduling meeting reminders in the specified channel
slack_scheduler.schedule_meeting_reminders("Your Channel ID")

# Starting the Slack scheduler to listen for commands and execute scheduled tasks
slack_scheduler.run()
