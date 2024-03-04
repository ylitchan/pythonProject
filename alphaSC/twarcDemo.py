from twarc import Twarc2, expansions
import json

# Replace your bearer token below
client = Twarc2(bearer_token="AAAAAAAAAAAAAAAAAAAAAPEGjQEAAAAAREb6WuXu7rNwm8ChnkpJoSJmSkw%3DXgtd6IlBg9SyrAcVhTOVucCrYL4OGfSjjCmMbfM8mFTi3CqUcL")


def main():
    # The following function gets users that the specified user follows
    following = client.following(user=4920186276)
    print(following)
    for page in following:
        result = expansions.flatten(page)
        for user in result:
            # Here we are printing the full Tweet object JSON to the console
            print(json.dumps(user))


if __name__ == "__main__":
    main()