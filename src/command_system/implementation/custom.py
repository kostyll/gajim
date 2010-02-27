# Copyright (C) 2009  Alexander Cherniuk <ts33kr@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
The module contains examples of how to create your own commands, by
creating a new command container and definding a set of commands.

Keep in mind that this module is not being loaded, so the code will not
be executed and commands defined here will not be detected.
"""

from ..framework import CommandContainer, command, documentation
from hosts import ChatCommands, PrivateChatCommands, GroupChatCommands

class CustomCommonCommands(CommandContainer):
    """
    This command container bounds to all three available in the default
    implementation command hosts. This means that commands defined in
    this container will be available to all - chat, private chat and a
    group chat.
    """

    HOSTS = (ChatCommands, PrivateChatCommands, GroupChatCommands)

    @command
    def dance(self):
        """
        First line of the doc string is called a description and will be
        programmatically extracted and formatted.

        After that you can give more help, like explanation of the
        options. This one will be programatically extracted and
        formatted too.

        After all the documentation - there will be autogenerated (based
        on the method signature) usage information appended. You can
        turn it off though, if you want.
        """
        return "I can't dance, you stupid fuck, I'm just a command system! A cool one, though..."

class CustomChatCommands(CommandContainer):
    """
    This command container bounds only to the ChatCommands command host.
    Therefore command defined here will be available only to a chat.
    """

    HOSTS = (ChatCommands,)

    @documentation(_("The same as using a doc-string, except it supports translation"))
    @command
    def sing(self):
        return "Are you phreaking kidding me? Buy yourself a damn stereo..."

class CustomPrivateChatCommands(CommandContainer):
    """
    This command container bounds only to the PrivateChatCommands
    command host.  Therefore command defined here will be available only
    to a private chat.
    """

    HOSTS = (PrivateChatCommands,)

    @command
    def make_coffee(self):
        return "What do I look like, you ass? A coffee machine!?"

class CustomGroupChatCommands(CommandContainer):
    """
    This command container bounds only to the GroupChatCommands command
    host.  Therefore command defined here will be available only to a
    group chat.
    """

    HOSTS = (GroupChatCommands,)

    @command
    def fetch(self):
        return "You should really buy yourself a dog and start torturing it instead of me..."
