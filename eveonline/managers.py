from __future__ import unicode_literals
from eveonline.models import EveCharacter
from eveonline.models import EveApiKeyPair
from eveonline.models import EveAllianceInfo
from eveonline.models import EveCorporationInfo
from eveonline.providers import eve_adapter_factory, EveXmlProvider
from services.managers.eve_api_manager import EveApiManager
import logging

logger = logging.getLogger(__name__)

adapter = eve_adapter_factory()

class EveManager:
    def __init__(self):
        pass

    @staticmethod
    def create_character(id, user, api_id):
        return EveManager.create_character_obj(adapter.get_character(id), user, api_id)

    @staticmethod
    def create_character_obj(character, user, api_id):
        EveCharacter.objects.create(
            character_id = character.id,
            character_name = character.name,
            corporation_id = character.corp.id,
            corporation_name = character.corp.name,
            alliance_id = character.alliance.id,
            alliance_name = character.alliance.name,
            user = user,
            api_id = api_id,
        )

    @staticmethod
    def create_xml_character(character_id, character_name, corporation_id,
                         corporation_name, corporation_ticker, alliance_id,
                         alliance_name, user, api_id):
        logger.debug("Creating model for character %s id %s" % (character_name, character_id))
        if not EveCharacter.objects.filter(character_id=character_id).exists():
            eve_char = EveCharacter()
            eve_char.character_id = character_id
            eve_char.character_name = character_name
            eve_char.corporation_id = corporation_id
            eve_char.corporation_name = corporation_name
            eve_char.corporation_ticker = corporation_ticker
            eve_char.alliance_id = alliance_id
            eve_char.alliance_name = alliance_name
            eve_char.user = user
            eve_char.api_id = api_id
            eve_char.save()
            logger.info("Created new character model %s for user %s" % (eve_char, user))
        else:
            logger.warn("Attempting to create existing character model with id %s" % character_id)

    @staticmethod
    def create_characters_from_list(chars, user, api_id):
        logger.debug("Creating characters from batch: %s" % chars.result)
        for char in chars.result:
            if not EveManager.check_if_character_exist(chars.result[char]['name']):
                EveManager.create_character(chars.result[char]['id'],
                                            chars.result[char]['name'],
                                            chars.result[char]['corp']['id'],
                                            chars.result[char]['corp']['name'],
                                            EveApiManager.get_corporation_ticker_from_id(
                                                chars.result[char]['corp']['id']),
                                            chars.result[char]['alliance']['id'],
                                            chars.result[char]['alliance']['name'],
                                            user, api_id)

    @staticmethod
    def update_character(id):
        return EveManager.update_character_obj(adapter.get_character(id))

    @staticmethod
    def update_character_obj(char):
        model = EveCharacter.objects.get(character_id=char.id)
        model.character_name = char.name
        model.corporation_id = char.corp.id
        model.corporation_name = char.corp.name
        model.alliance_id = char.alliance.id
        model.alliance_name = char.alliance.name
        model.save()

    @staticmethod
    def update_characters_from_list(chars):
        logger.debug("Updating characters from list: %s" % chars.result)
        for char in chars.result:
            if EveManager.check_if_character_exist(chars.result[char]['name']):
                eve_char = EveManager.get_character_by_character_name(chars.result[char]['name'])
                logger.debug("Got existing character model %s" % eve_char)
                eve_char.corporation_id = chars.result[char]['corp']['id']
                eve_char.corporation_name = chars.result[char]['corp']['name']
                eve_char.corporation_ticker = EveApiManager.get_corporation_ticker_from_id(
                    chars.result[char]['corp']['id'])
                eve_char.alliance_id = chars.result[char]['alliance']['id']
                eve_char.alliance_name = chars.result[char]['alliance']['name']
                eve_char.save()
                logger.info("Updated character model %s" % eve_char)
            else:
                logger.warn(
                    "Attempting to update non-existing character model with name %s" % chars.result[char]['name'])

    @staticmethod
    def create_api_keypair(api_id, api_key, user_id):
        logger.debug("Creating api keypair id %s for user_id %s" % (api_id, user_id))
        if not EveApiKeyPair.objects.filter(api_id=api_id).exists():
            api_pair = EveApiKeyPair()
            api_pair.api_id = api_id
            api_pair.api_key = api_key
            api_pair.user = user_id
            api_pair.save()
            logger.info("Created api keypair id %s for user %s" % (api_id, user_id))
        else:
            logger.warn("Attempting to create existing api keypair with id %s" % api_id)

    @staticmethod
    def create_alliance(id, is_blue=False):
        return EveManager.create_alliance_obj(adapter.get_alliance(id), is_blue=is_blue)

    @staticmethod
    def create_alliance_obj(alliance, is_blue=False):
        EveAllianceInfo.objects.create(
            alliance_id = alliance.id,
            alliance_name = alliance.name,
            alliance_ticker = alliance.ticker,
            executor_corp_id = alliance.executor_corp_id,
            is_blue = is_blue,
        )

    @staticmethod
    def update_alliance(id, is_blue=None):
        return EveManager.update_alliance_obj(adapter.get_alliance(id), is_blue=is_blue)

    @staticmethod
    def update_alliance_obj(alliance, is_blue=None):
        model = EveAllianceInfo.objects.get(alliance_id=alliance.id)
        model.executor_corp_id = alliance.executor_corp_id
        model.is_blue = model.is_blue if is_blue == None else is_blue
        model.save()

    @staticmethod
    def populate_alliance(id):
        alliance_model = EveAllianceInfo.objects.get(alliance_id=id)
        alliance = adapter.get_alliance(id)
        for corp_id in alliance.corp_ids:
            if not EveCorporationInfo.objects.filter(corporation_id=corp_id).exists():
               EveManager.create_corporation(corp_id, is_blue=alliance_model.is_blue)
        EveCorporationInfo.objects.filter(corporation_id__in=alliance.corp_ids).update(alliance=alliance_model)
        EveCorporationInfo.objects.filter(alliance=alliance_model).exclude(corporation_id__in=alliance.corp_ids).update(alliance=None)
            

    @staticmethod
    def create_corporation(id, is_blue=False):
        return EveManager.create_corporation_obj(adapter.get_corp(id), is_blue=is_blue)

    @staticmethod
    def create_corporation_obj(corp, is_blue=False):
        try:
            alliance = EveAllianceInfo.objects.get(alliance_id=corp.alliance_id)
        except EveAllianceInfo.DoesNotExist:
            alliance = None
        EveCorporationInfo.objects.create(
            corporation_id = corp.id,
            corporation_name = corp.name,
            corporation_ticker = corp.ticker,
            member_count = corp.members,
            alliance = alliance,
            is_blue = is_blue,
        )

    @staticmethod
    def update_corporation(id, is_blue=None):
        return EveManager.update_corporation_obj(adapter.get_corp(id), is_blue=is_blue)

    @staticmethod
    def update_corporation_obj(corp, is_blue=None):
        model = EveCorporationInfo.objects.get(corporation_id=corp.id)
        model.member_count = corp.members
        try:
            model.alliance = EveAllianceInfo.objects.get(alliance_id=corp.alliance_id)
        except EveAllianceInfo.DoesNotExist:
            model.alliance = None
        model.is_blue = model.is_blue if is_blue == None else is_blue
        model.save()

    @staticmethod
    def get_characters_from_api(api):
        char_result = EveApiManager.get_characters_from_api(api.api_id, api.api_key).result
        provider = EveXmlProvider(adapter=adapter)
        return [provider._build_character(result) for id, result in char_result.items()]

    @staticmethod
    def get_api_key_pairs(user):
        if EveApiKeyPair.objects.filter(user=user).exists():
            logger.debug("Returning api keypairs for user %s" % user)
            return EveApiKeyPair.objects.filter(user=user)
        else:
            logger.debug("No api keypairs found for user %s" % user)

    @staticmethod
    def check_if_api_key_pair_exist(api_id):
        if EveApiKeyPair.objects.filter(api_id=api_id).exists():
            logger.debug("Determined api id %s exists." % api_id)
            return True
        else:
            logger.debug("Determined api id %s does not exist." % api_id)
            return False

    @staticmethod
    def check_if_api_key_pair_is_new(api_id, fudge_factor):
        if EveApiKeyPair.objects.count() == 0:
            return True
        latest_api_id = int(EveApiKeyPair.objects.order_by('-api_id')[0].api_id) - fudge_factor
        if latest_api_id >= api_id:
            logger.debug("api key (%d) is older than latest API key (%d). Rejecting" % (api_id, latest_api_id))
            return False
        else:
            logger.debug("api key (%d) is new. Accepting" % api_id)
            return True

    @staticmethod
    def delete_api_key_pair(api_id, user_id):
        logger.debug("Deleting api id %s" % api_id)
        if EveApiKeyPair.objects.filter(api_id=api_id).exists():
            # Check that its owned by our user_id
            apikeypair = EveApiKeyPair.objects.get(api_id=api_id)
            if apikeypair.user.id == user_id:
                logger.info("Deleted user %s api key id %s" % (user_id, api_id))
                apikeypair.delete()
            else:
                logger.error(
                    "Unable to delete api: user mismatch: key id %s owned by user id %s, not deleting user id %s" % (
                        api_id, apikeypair.user.id, user_id))
        else:
            logger.warn("Unable to locate api id %s - cannot delete." % api_id)

    @staticmethod
    def delete_characters_by_api_id(api_id, user_id):
        logger.debug("Deleting all characters associated with api id %s" % api_id)
        if EveCharacter.objects.filter(api_id=api_id).exists():
            # Check that its owned by our user_id
            characters = EveCharacter.objects.filter(api_id=api_id)
            logger.debug("Got user %s characters %s from api %s" % (user_id, characters, api_id))
            for char in characters:
                if char.user.id == user_id:
                    logger.info("Deleting user %s character %s from api %s" % (user_id, char, api_id))
                    char.delete()
                else:
                    logger.error(
                        "Unable to delete character %s by api %s: user mismatch: character owned by user id %s, "
                        "not deleting user id %s" % (
                            char, api_id, char.user.id, user_id))

    @staticmethod
    def check_if_character_exist(char_name):
        return EveCharacter.objects.filter(character_name=char_name).exists()

    @staticmethod
    def get_characters_by_owner_id(user):
        if EveCharacter.objects.filter(user=user).exists():
            return EveCharacter.objects.all().filter(user=user)

        return None

    @staticmethod
    def get_character_by_character_name(char_name):
        if EveCharacter.objects.filter(character_name=char_name).exists():
            return EveCharacter.objects.get(character_name=char_name)

    @staticmethod
    def get_character_by_id(char_id):
        if EveCharacter.objects.filter(character_id=char_id).exists():
            return EveCharacter.objects.get(character_id=char_id)

        return None

    @staticmethod
    def get_charater_alliance_id_by_id(char_id):
        if EveCharacter.objects.filter(character_id=char_id).exists():
            return EveCharacter.objects.get(character_id=char_id).alliance_id

    @staticmethod
    def check_if_character_owned_by_user(char_id, user):
        character = EveCharacter.objects.get(character_id=char_id)

        if character.user.id == user.id:
            return True

        return False

    @staticmethod
    def check_if_alliance_exists_by_id(alliance_id):
        return EveAllianceInfo.objects.filter(alliance_id=alliance_id).exists()

    @staticmethod
    def check_if_corporation_exists_by_id(corp_id):
        return EveCorporationInfo.objects.filter(corporation_id=corp_id).exists()

    @staticmethod
    def get_alliance_info_by_id(alliance_id):
        if EveManager.check_if_alliance_exists_by_id(alliance_id):
            return EveAllianceInfo.objects.get(alliance_id=alliance_id)
        else:
            return None

    @staticmethod
    def get_corporation_info_by_id(corp_id):
        if EveManager.check_if_corporation_exists_by_id(corp_id):
            return EveCorporationInfo.objects.get(corporation_id=corp_id)
        else:
            return None

    @staticmethod
    def get_all_corporation_info():
        return EveCorporationInfo.objects.all()

    @staticmethod
    def get_all_alliance_info():
        return EveAllianceInfo.objects.all()

    @staticmethod
    def get_charater_corporation_id_by_id(char_id):
        if EveCharacter.objects.filter(character_id=char_id).exists():
            return EveCharacter.objects.get(character_id=char_id).corporation_id
