"""Docker and local entry. Importing this module does not open a broker connection."""

if __name__ == "__main__":
    from quantos.api.http import main

    main()
