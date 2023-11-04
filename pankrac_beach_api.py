import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import json


def get_data(date):
    day, month, year = date.split("-")
    url = f"https://beachklub.isportsystem.cz/ajax/ajax.schema.php?day={day}&month={month}&year={year}&id_sport=1&default_view=day&reset_date=0&event=changeWeek&id_infotab=0&time=&filterId=false&filterChecked=false&tab_type=normal&numberOfDays=0&display_type=undefined&labels=undefined&lastTimestamp=undefined&_=1698575957836"
    response = requests.get(url)
    return response


def get_raw_times(res):
    soup = BeautifulSoup(res.content, "html.parser")

    # Find all <div> or <td> elements with class="empty tooltip" or class="booked tooltip"
    elements = soup.find_all(
        ["div", "td", "a"], {"class": ["empty tooltip", "booked tooltip", "tooltip"]}
    )

    # Initialize index variable
    times = []
    index = 0

    titles = [i["title"] for i in elements]
    min_time = min([int(value.split("–")[0].split(":")[0]) for value in titles[1:]])
    # Loop through each element and extract the title attribute
    for element in elements:
        title = element["title"].strip()
        if re.search(rf"\b{min_time}:00\b", title):
            index += 1
        times.append(title + " - kurt " + str(index))

    times_updated = [t.replace("Zavřeno", "- Zavřeno") for t in times]

    return times_updated[1:]


def create_dataframe(updated_times):
    df = pd.DataFrame(updated_times, columns=["Time"])
    df["Time"] = updated_times
    df[["Times", "status", "court"]] = df["Time"].str.split("-", expand=True)
    df[["Start Time", "End Time"]] = df["Times"].str.split("–", expand=True)
    df.drop(["Times", "Time"], axis=1, inplace=True)
    return df


def format_dataframe(df):
    expanded_times = []
    for i, row in df.iterrows():
        start_hour, star_minute = row["Start Time"].split(":")
        end_hour, end_minute = row["End Time"].split(":")

        start_date = datetime.datetime(
            2022, 1, 1, int(start_hour), int(star_minute)
        )  # January 1st, 2022 at 8:00 AM
        end_date = datetime.datetime(
            2022, 1, 1, int(end_hour), int(end_minute)
        )  # January 1st, 2022 at 5:00 PM
        interval = datetime.timedelta(minutes=30)

        # Create array of times
        times = []
        current_time = start_date
        while current_time <= end_date:
            times.append(current_time.strftime("%H:%M"))
            current_time += interval

        # Print array of times
        expanded_times.append(times)

    df["expanded_times"] = expanded_times
    df = df.explode("expanded_times")

    df = df[["expanded_times", "status", "court"]].drop_duplicates()
    df = df.drop_duplicates(["expanded_times", "court"], keep="last")
    mask = ~df["expanded_times"].str.contains("22:00")
    df = df[mask]

    return df


def parse_date(res):
    pattern = r"\b\d{1,2}-\d{1,2}-\d{4}\b"
    dates = re.findall(pattern, res)
    return dates


def get_free_slots(date):
    res = get_data(date)
    times = get_raw_times(res)
    df = create_dataframe(times)
    # df = format_dataframe(df)
    df.to_csv("data.csv", index=False)
    # free = df[df["status"] == " Volno "]
    return df


def get_free_days(date_arr):
    result_df = pd.DataFrame()

    for date in date_arr:
        free = get_free_slots(date)
        free["date"] = date
        if len(free) > 0:
            free_df = pd.DataFrame(free)
            result_df = pd.concat([result_df, free_df])

    result_df.to_csv("free_days.csv", index=True)

    return result_df


def get_dates(start_date, end_date):
    """
    Returns a list of dates between start_date and end_date (inclusive)
    """
    start = datetime.datetime.strptime(start_date, "%d-%m-%Y")
    end = datetime.datetime.strptime(end_date, "%d-%m-%Y")
    delta = end - start
    dates = []
    for i in range(delta.days + 1):
        date = start + datetime.timedelta(days=i)
        dates.append(date.strftime("%d-%m-%Y"))
    return dates


def get_time_period(str_def=None, start_date=None, end_date=None):
    """
    Returns a tuple of start and end dates based on the input string and optional end date.

    Args:
        str_def (str): A string defining the time period. Possible values are "today", "tomorrow", "week", "2weeks"
        end_date (str, optional): A string representing the end date in the format "%d-%m-%Y". Defaults to None.

    Returns:
        tuple: A tuple of start and end dates in the format "%d-%m-%Y".
    """

    if str_def is None:
        if start_date is None:
            start_date = datetime.datetime.now().strftime("%d-%m-%Y")

        else:
            start_date = datetime.datetime.strptime(start_date, "%d-%m-%Y").strftime(
                "%d-%m-%Y"
            )

        if end_date is None:
            print("Please provide an end date in DD-MM-YYYY format")
            return None

        else:
            end_date = datetime.datetime.strptime(end_date, "%d-%m-%Y").strftime(
                "%d-%m-%Y"
            )

        return get_dates(start_date, end_date)

    if str_def == "today":
        start_date = datetime.datetime.now().strftime("%d-%m-%Y")
        end_date = datetime.datetime.now().strftime("%d-%m-%Y")
        return get_dates(start_date, end_date)
    elif str_def == "tomorrow":
        start_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime(
            "%d-%m-%Y"
        )
        end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime(
            "%d-%m-%Y"
        )
        return get_dates(start_date, end_date)
    elif str_def == "week":
        start_date = datetime.datetime.now().strftime("%d-%m-%Y")
        end_date = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime(
            "%d-%m-%Y"
        )
        return get_dates(start_date, end_date)
    elif str_def == "2weeks":
        start_date = datetime.datetime.now().strftime("%d-%m-%Y")
        end_date = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime(
            "%d-%m-%Y"
        )
        return get_dates(start_date, end_date)
    else:
        return get_dates(start_date, end_date)


def find_available_slots(table_data, slot_duration):
    available_slots = []
    current_slot_start = None
    current_slot_status = None

    for entry in table_data:
        start = entry["Start Time"]
        end = entry["End Time"]
        status = entry["status"]
        court = entry["court"]
        date = entry["date"]

        if current_slot_status is None:
            current_slot_start = start
            current_slot_status = status
        elif current_slot_status != status:
            if current_slot_status == " Volno ":
                available_slots.append((current_slot_start, end, court, date))
            current_slot_start = start
            current_slot_status = status

    if current_slot_status == " Volno ":
        available_slots.append((current_slot_start, end, court, date))

    # Group slots by the specified duration
    grouped_slots = []

    slot_duration_minutes = slot_duration

    for start, end, court, date in available_slots:
        start_time = int(start.split(":")[0]) * 60 + int(start.split(":")[1])
        end_time = int(end.split(":")[0]) * 60 + int(end.split(":")[1])
        court = court
        date = date

        while start_time + slot_duration_minutes <= end_time:
            end_slot_time = start_time + slot_duration_minutes
            start_slot = f"{start_time // 60:02d}:{start_time % 60:02d}"
            end_slot = f"{end_slot_time // 60:02d}:{end_slot_time % 60:02d}"
            grouped_slots.append((start_slot, end_slot, court, date))
            start_time = end_slot_time

    return grouped_slots


def get_available_slots(time_frac=None, start_date=None, end_date=None, group_by=[60]):
    """
    Returns list of available dates based on time_frac or definition of time periond (start and end dates)
    If no start date is provided, the current date is used as the start date.

    Args:
        time_frac (str): A string defining the time period. Possible values are "today", "tomorrow", "week", "2weeks", "3weeks".
        end_date (str, optional): A string representing the end date in the format "%d-%m-%Y". Defaults to None.

    Returns:
        list: list of available dates".
    """
    dates = get_time_period(str_def=time_frac, start_date=start_date, end_date=end_date)
    all_values = get_free_days(dates)
    json_values = json.loads(all_values.to_json(orient="records"))

    slot_durations = group_by
    for slot_duration in slot_durations:
        available_slots = find_available_slots(json_values, slot_duration)
        print(f"Grouped by {slot_duration}:")

    df = pd.DataFrame(available_slots, columns=["start", "end", "court", "date"])
    return df

    # for start, end, court, date in available_slots:
    #     print(f"{start} to {end} - available {court} - {date}")


if __name__ == "__main__":
    df = get_available_slots(
        start_date="09-11-2023", end_date="10-11-2023", group_by=[90]
    )


df.groupby(["date", "court"])["court"].count()
