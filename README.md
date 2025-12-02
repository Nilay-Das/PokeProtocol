# PokeProtocol
This project simulates a pokemon battle between two peers using a predefined communication mode (Broadcast or P2P)  
Peers can take on three roles a host, joiner, and spectator  
Hosts are responsible for hosting the game proper and providing information such as the game seed  
Joiners join hosts as the 2nd player, spectators can only join an existing game  
Hosts and spectators exchange battle messages and chat messages, spectators can see these messages and send their chats but cannot issues battle commands  

How to Run  
-- As a Host --  
Choose your communication mode (P2P, Broadcast)  
Choose a pokemon by entering its Pokedex ID  
Name yourself  
Choose the IP and Port you wish to bind to  
Wait for Joiners to connect, you will have the ability to reject or accept them  

-- As a Joiner --  
Choose your communication mode (P2P, Broadcast)  
Indicate the Host IP and Port you wish to bind to  
Choose a pokemon by entering its Pokedex ID  
Name yourself  
Wait for the host to accept your connection  

-- As a Spectator --  
Choose the Host IP and Port you wish to listen on  
Set a name  
Wait for the host to accept your connection  
Note: Spectators are automatically accepted by hosts  

-- Battle Comnmands --  
!attack -> send an attack to the opponent (Only designated attackers can attack, if it is not your turn you cannot attack)  
!chat -> send a chat to the opponent (You can send these at any time)  
Note: Spectators cannot use !attack, they can only send chats to the host  

All connections close once either the host or joiner faints.  
All other functions such as CALCULATION_REPORT, DEFENSE_ANNOUNCE, etc. are handled automatically and do not require User Input  
If choosing Broadcast as your mode of communication, entering a host IP is ommitted and you are automically bound to 0.0.0.0 and will send to 255.255.255.255  
  
**AI DECLARATION**  
We as a group have used AI for the following:  
Initial brainstorming of how battle states should work  
Structure of the files (Base Peer Class, Message Factory)
Summarization of the socket library documentation (asking ChatGPT what a specific function does)  
Creation of test cases (exception handling for user input, simulation of disconnects and possible issues that may arise while running)    
Asking for sources of similar projects/examples of UDP connection programs online  
