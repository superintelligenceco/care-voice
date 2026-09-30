# Records docs/assets/demo.gif from a real run of care-voice.
#
#   vhs docs/demo.tape
#
# The check-in is answered live in the terminal simulator, then the stored
# alerts are listed from the SQLite history.
Output docs/assets/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1240
Set Height 720
Set Padding 16
Set TypingSpeed 35ms
Set Theme "Catppuccin Mocha"

Hide
Type "export PS1='$ ' && cd $(mktemp -d) && clear"
Enter
Show

Type "care-voice --version"
Sleep 300ms
Enter
Sleep 1s

Type "care-voice simulate --name Margaret --date 2026-09-30 --db demo.db"
Sleep 300ms
Enter
Sleep 1.5s

Type "Not really, I kept waking up"
Enter
Sleep 900ms
Type "No, I forgot them"
Enter
Sleep 900ms
Type "Yes, some toast"
Enter
Sleep 900ms
Type "Yes, my hip hurts"
Enter
Sleep 900ms
Type "About an eight"
Enter
Sleep 900ms
Type "My right hip"
Enter
Sleep 900ms
Type "I slipped in the bathroom last night"
Enter
Sleep 900ms
Type "Is it Sunday?"
Enter
Sleep 900ms
Type "Pretty low today"
Enter
Sleep 4s

Type "clear && care-voice alerts --db demo.db"
Sleep 300ms
Enter
Sleep 5s
