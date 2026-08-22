[English](SECURITY.md) | [Français](SECURITY.fr.md)

# Politique de sécurité

## Signaler une vulnérabilité

Utilisez le signalement privé de vulnérabilité GitHub lorsqu’il est activé. Ne publiez pas d’identifiants VPN, de clés WireGuard, de topologie réseau privée, de jetons d’accès ou de détails d’exploitation dans une issue publique.

Pour un bug de routage ou de lecture ordinaire, ouvrez une issue classique avec la version de Kodi, la version de LibreELEC/Linux, les versions des extensions et un extrait de journal expurgé.

## Comportement local privilégié

Cette extension exécute de manière synchrone deux scripts shell locaux. Ces scripts peuvent modifier la route par défaut de l’hôte et interagir avec ConnMan/WireGuard. Considérez les fichiers placés sous `/storage/.config/` comme une configuration locale privilégiée et limitez les personnes pouvant les modifier.

Le dépôt contient volontairement uniquement des scripts de référence génériques et un exemple de configuration utilisant des valeurs de documentation. Les vraies adresses d’endpoint, identifiants VPN, clés privées et valeurs d’infrastructure locale doivent rester uniquement dans la copie locale.

## Validation des entrées de failover

Les helpers purs de `failover.py` bornent la taille compressée et décompressée du payload, limitent le nombre de sources, valident les noms de route autorisés et n’acceptent que des cibles plugin Kodi ou HTTP(S). Une boucle vers `plugin.video.therandtv` est refusée.

## Données sensibles

Ne versionnez jamais :

- des clés privées WireGuard ou des configurations client complètes ;
- des noms d’utilisateur, mots de passe ou jetons VPN ;
- des identifiants ou cookies de playlists privées ;
- des détails d’infrastructure personnelle qui ne sont pas volontairement publics.

Expurgez ces valeurs des journaux avant de les partager.
