decklog_parser.py 
  This script pulls a specific deck code from the bushiroad website and then parses the card data to give english links to the shadowverse website and tcgplayer
  usage: python decklog_parser.py DECKCODE
    If you want the output as a JSON file (used in the next script) run like this
    python decklog_parser.py DECKCODE > OUTPUTFILENAME

build_deck_site.py
  This script takes the JSON output from the previous script and then creates an HTML file that presents the information in an easier way to view.
  usage: python build_deck_site.py INPUTJSONNAME OUTPUTHTMLNAME
