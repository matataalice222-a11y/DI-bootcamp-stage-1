import random

def number_guessing_game():
    random_number = random.randint(1, 100)
    print("Welcome to the Number Guessing Game!")
    max_attempts = 7
    
    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}/{max_attempts}")
        guess = int(input(f"Attempt {attempt}/{max_attempts} - Enter your guess: "))
        print(f"You guessed: {guess}")
        
        if guess < random_number:
            print("Too low!")
            print(f"You have {max_attempts - attempt} attempts left.")
        elif guess > random_number:
            print("Too high!")
            print(f"You have {max_attempts - attempt} attempts left.")
        else:
            print(f"Congratulations! You guessed the correct number ({random_number})!")
            print(f"You used {attempt} attempts.")
            break
    else:
        # Executes only if the loop finishes without breaking (i.e., player ran out of attempts)
        print(f"Game over! You've used all your attempts. The correct number was {random_number}.")
        print(f"You used {max_attempts} attempts.")

# Call the function to start the game
number_guessing_game()
print()
print("Thank you for playing the Number Guessing Game!")    