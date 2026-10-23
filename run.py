from predictor import Predictor

#collect user input based on input_type and determines if input is valid
def collect_input(wordle, input_type):
    if input_type == "guess":
        response = input("\nPlease enter guess: ")
        condition = response in wordle.available

    elif input_type == "rule":
        input_string = "\nPlease input the given rule. "
        input_string += "Type it in as a 5 letter word (g, y, or b): "
        response = input(input_string)
        condition = False
        if len(response) == 5:
            condition = sum([wordle.single_letter_count(response, i) for i in ["g", "y", "b"]]) == 5

    elif input_type == "ev_valid":
        response = input("\nWould you like to calculate expected valid size for potential solutions? (y/n) ")
        condition = (response == "y") or (response == "n")
    
    elif input_type == "ev_weighted":
        response = input("\nWould you like to calculate expectation weighted valid size for potential solutions? (y/n) ")
        condition = (response == "y") or (response == "n")

    elif input_type == "keep_trying":
        response = input("\nGuesses are used up! Would you like to keep trying? (y/n) ")
        condition = (response == "y") or (response == "n")

    return response, condition

#process input according to input_type, catch for errors, or quit
def process_input(wordle, input_type):
    prompt = True
    while prompt: #continue to prompt until valid input or quit
        response, condition = collect_input(wordle, input_type)

        if response == "q" or response == "quit":
            print("\nThanks for using the Wordle Solving A.I. Interface. Have a good day!")
            raise SystemExit
        elif condition: #valid input
            prompt = False
        else:
            print("Invalid input.")

    return response

#generate output ideal for analysis
def print_reports(wordle):
    print("\nList of words is", len(wordle.valid), "long.")

    #frequency
    print("\n10 highest remaining solutions by frequency:")
    print(wordle.get_frequencies().head(10))

    #expected size
    response = process_input(wordle, "ev_valid")
    if response == "y":
        print(wordle.expected_valid_size(valid = True, word_freq = False).head(10))
    
    #expected size of invalid guesses
    response = process_input(wordle, "ev_weighted")
    if response == "y":
        print(wordle.expected_valid_size(valid = True, word_freq = True).head(10))
    
#open prompt to quickly make guesses and input rules
def run_game_interface(wordle):
    print("\nWelcome to Wordle Solving A.I. Interface.")
    print("Designed for quick input/output with a variety of analytic tools.")
    print("Type \"q\" or \"quit\" anytime to quit.")
    counter = 0
    keep_trying = True

    while keep_trying:
        guess = process_input(wordle, "guess") #input

        if len(wordle.valid) == 1: #only one possible guess
            if wordle.valid[0] == guess: #guessed only remaining
                print("\nCongratulations! You solved the Wordle.") #in n guesses
                keep_trying = False
            else:
                print("\nThe solution is", wordle.valid[0] + ".")
                keep_trying = False
        else:
            raw_rule = process_input(wordle, "rule") #prompt for rule
            rule = wordle.parse_rule(raw_rule)

            if wordle.single_letter_count(raw_rule, "g") == 5: 
                print("\nCongratulations! You solved the Wordle.")
                keep_trying = False

            else:
                wordle.update_valid(guess, rule) #analysis
                print_reports(wordle)

                counter += 1
                if counter == 6:
                    keep_trying_input = process_input(wordle, "keep_trying")
                    keep_trying = (keep_trying_input == "y")

    print("\nThanks for using the Wordle Solving A.I. Interface. Have a good day!")

wordle = Predictor()
run_game_interface(wordle)