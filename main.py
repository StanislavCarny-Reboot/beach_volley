from pankrac_beach_api import get_available_slots


if __name__ == "__main__":
    # USAGE:
    get_available_slots("tomorrow", group_by=[90])
    get_available_slots(end_date="6-11-2023", group_by=[90])
    get_available_slots(start_date="5-11-2023", end_date="6-11-2023", group_by=[90])
